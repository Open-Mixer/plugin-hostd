# SPDX-License-Identifier: GPL-3.0-or-later
# own_host_lv2_probe.py drives libjack through ctypes; libjack answers jack_activate() by starting a realtime
# thread that keeps firing the process callback until the client is deactivated and closed. A probe that returns
# from main() without jack_deactivate/jack_client_close leaves that thread racing the interpreter's teardown: when
# the thread's next callback lands while CPython is finalizing, the ctypes trampoline calls into freed interpreter
# state and the process dies with SIGSEGV (returncode -11, which a wrapping shell/CI reports as 245 -
# plugin-hostd#110). This builds a fake libjack.so.0 whose RT thread callbacks at a busy, uncapped rate - so the
# race is hit on close to every run instead of rarely - loops the real probe through a full settle+measure cycle
# (connected to the ports the fake target publishes by LV2 symbol, never to a fixed in_N name: plugin-hostd#320)
# against it TRIALS times, and requires every run to exit 0 with no crash.
#
#   python3 tests/own_host_lv2_probe_teardown_test.py
import ctypes, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "tests", "own_host_lv2_probe.py")
CC = os.environ.get("CC", "cc")
TRIALS = int(os.environ.get("OWN_HOST_LV2_PROBE_TEARDOWN_TRIALS", "8"))

# A fake libjack: a single own-host-probe client, and a target "fx" that publishes its ports by LV2 symbol, as
# omx-clap-host names an LV2 plugin's (plugin-hostd#320): fx:lv2_in_1/2 and fx:lv2_out_1/2, wired as a zero-latency
# unity-gain pass-through; a connect to a port fx does not publish fails, as JACK's does (so the probe's own gain check sees ratio 1.0 and takes its success path,
# the path the issue's crash was seen on). jack_activate spawns the RT thread; only jack_deactivate stops it and
# joins it, matching real libjack closely enough to race a probe that skips the call.
FAKE_JACK_C = r'''
#include <pthread.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

typedef int (*phd_cb)(uint32_t, void *);

typedef struct { char name[32]; float buf[4096]; } port_t;
typedef struct { float *src, *dst; } conn_t;

static port_t g_ports[8];
static int g_nports;
static float g_virt[4][4096];
static conn_t g_conns[8];
static int g_nconns;
static phd_cb g_cb;
static void *g_arg;
static volatile int g_active;
static pthread_t g_thread;

static const char *const g_fx_in[] = { "fx:lv2_in_1", "fx:lv2_in_2", 0 };
static const char *const g_fx_out[] = { "fx:lv2_out_1", "fx:lv2_out_2", 0 };

static int published(const char *qualified)
{
    int i;

    if (strncmp(qualified, "own-host-probe:", 15) == 0)
        return 1;
    for (i = 0; g_fx_in[i]; i++)
        if (!strcmp(qualified, g_fx_in[i]) || !strcmp(qualified, g_fx_out[i]))
            return 1;
    return 0;
}

const char **jack_get_ports(void *client, const char *name, const char *type, unsigned long flags)
{
    static const char *list[3];
    const char *const *src = (flags & 1) ? g_fx_in : g_fx_out;
    int i;

    (void)client; (void)type;
    if (!name || strcmp(name, "^fx:") != 0)
        return 0;
    for (i = 0; src[i]; i++)
        list[i] = src[i];
    list[i] = 0;
    return list;
}

void jack_free(void *p)
{
    (void)p;
}

static float *resolve(const char *qualified)
{
    const char *colon = strrchr(qualified, ':');
    const char *base = colon ? colon + 1 : qualified;
    int i, v;

    if (strncmp(qualified, "own-host-probe:", 15) == 0)
    {
        for (i = 0; i < g_nports; i++)
            if (!strcmp(g_ports[i].name, base))
                return g_ports[i].buf;
    }
    v = base[strlen(base) - 1] - '1';
    if (v < 0 || v > 3)
        v = 0;
    return g_virt[v];
}

static void *driver(void *unused)
{
    (void)unused;
    while (g_active)
    {
        int i;

        if (g_cb)
            g_cb(256, g_arg);
        for (i = 0; i < g_nconns; i++)
            memcpy(g_conns[i].dst, g_conns[i].src, 256 * sizeof(float));
        usleep(200);
    }
    return 0;
}

void *jack_client_open(const char *name, int options, void *status)
{
    (void)name; (void)options; (void)status;
    return (void *)1;
}

void *jack_port_register(void *client, const char *name, const char *type, unsigned long flags, unsigned long bufsize)
{
    port_t *p = &g_ports[g_nports++];

    (void)client; (void)type; (void)flags; (void)bufsize;
    strncpy(p->name, name, sizeof(p->name) - 1);
    return p->buf;
}

void *jack_port_get_buffer(void *port, uint32_t n)
{
    (void)n;
    return port;
}

void jack_set_process_callback(void *client, phd_cb cb, void *arg)
{
    (void)client;
    g_cb = cb;
    g_arg = arg;
}

uint32_t jack_get_sample_rate(void *client)
{
    (void)client;
    return 48000;
}

int jack_activate(void *client)
{
    (void)client;
    g_active = 1;
    pthread_create(&g_thread, 0, driver, 0);
    return 0;
}

int jack_connect(void *client, const char *a, const char *b)
{
    (void)client;
    if (!published(a) || !published(b))
        return -1;
    g_conns[g_nconns].src = resolve(a);
    g_conns[g_nconns].dst = resolve(b);
    g_nconns++;
    return 0;
}

int jack_deactivate(void *client)
{
    (void)client;
    g_active = 0;
    pthread_join(g_thread, 0);
    return 0;
}

int jack_client_close(void *client)
{
    (void)client;
    return 0;
}
'''


def build_fake_jack(dirpath):
    so = os.path.join(dirpath, "libjack.so.0")
    src = os.path.join(dirpath, "fake_jack.c")
    with open(src, "w") as f:
        f.write(FAKE_JACK_C)
    subprocess.run([CC, "-shared", "-fPIC", "-O2", "-pthread", "-o", so, src], check=True)
    return so


def run_probe(libdir):
    env = dict(os.environ, LD_LIBRARY_PATH=libdir + ":" + os.environ.get("LD_LIBRARY_PATH", ""))
    p = subprocess.run([sys.executable, PROBE, "fx", "1.0", "0.0005"], cwd=libdir, env=env,
                       capture_output=True, text=True, timeout=20)
    return p.returncode, p.stdout, p.stderr


def main():
    with tempfile.TemporaryDirectory() as d:
        build_fake_jack(d)
        crashes = []
        for trial in range(TRIALS):
            rc, out, err = run_probe(d)
            if rc != 0:
                crashes.append((trial, rc, out.strip(), err.strip()))
        if crashes:
            for trial, rc, out, err in crashes:
                print("FAIL own_host_lv2_probe_teardown_test: trial %d exited %d\n%s\n%s" % (trial, rc, out, err))
            print("FAIL own_host_lv2_probe_teardown_test: %d/%d runs did not exit cleanly against a busy fake "
                  "libjack RT thread" % (len(crashes), TRIALS))
            return 1
        print("ok   own_host_lv2_probe_teardown_test: %d/%d runs exited cleanly against a busy fake libjack RT thread"
              % (TRIALS, TRIALS))
        return 0


if __name__ == "__main__":
    sys.exit(main())
