# SPDX-License-Identifier: GPL-3.0-or-later
# Proves a JACK client processes audio: plays a sine into the client's audio inputs and measures the peak that comes out
# of its audio outputs through libjack, with nothing but python3 and the JACK library the page installs. The ports are
# the ones the client publishes, read from JACK in the order it registered them, never a fixed name: omx-clap-host names
# an LV2 plugin's ports by their LV2 symbols, as mod-host does (plugin-hostd#320). It exits
# 0 only when out/in is within <tolerance> of <gain>, the linear gain the plugin was set to (a silent or unprocessed
# output measures 0 or 1).
#
#   own_host_lv2_probe.py <client> <gain> <tolerance>
import ctypes, math, sys, time

PORT_IS_INPUT, PORT_IS_OUTPUT = 1, 2
AMPLITUDE = 0.25
HZ = 1000.0
SETTLE_S, MEASURE_S = 1.5, 1.5
PORTS_WAIT_S = 5.0

CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p)


def ports(jack, c, target, flags):
    """the audio ports of `target` of one direction, as JACK lists them"""
    # JACK matches a POSIX extended regex: only its special characters are escaped
    pattern = ("^" + "".join("\\" + ch if ch in ".[]()*+?{}|^$\\" else ch for ch in target) + ":").encode()
    found = jack.jack_get_ports(c, pattern, b"audio", flags)
    names = []
    if found:
        k = 0
        while found[k]:
            names.append(found[k].decode())
            k += 1
        jack.jack_free(ctypes.cast(found, ctypes.c_void_p))
    return names


def published(jack, c, target):
    """the client's audio inputs and outputs, once it has at least one of each, waiting a bounded time for them"""
    deadline = time.monotonic() + PORTS_WAIT_S
    while True:
        t_in, t_out = ports(jack, c, target, PORT_IS_INPUT), ports(jack, c, target, PORT_IS_OUTPUT)
        if (t_in and t_out) or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    if not t_in or not t_out:
        sys.exit("own_host_lv2_probe: %s publishes no audio %s port (inputs %s, outputs %s)"
                 % (target, "input" if not t_in else "output", t_in, t_out))
    print("own_host_lv2_probe: %s publishes inputs %s, outputs %s" % (target, t_in, t_out))
    return t_in, t_out


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: own_host_lv2_probe.py <client> <gain> <tolerance>")
    target, want, tol = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    jack = ctypes.CDLL("libjack.so.0")
    jack.jack_client_open.restype = ctypes.c_void_p
    jack.jack_client_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
    jack.jack_port_register.restype = ctypes.c_void_p
    jack.jack_port_register.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong]
    jack.jack_port_get_buffer.restype = ctypes.c_void_p
    jack.jack_port_get_buffer.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    jack.jack_set_process_callback.argtypes = [ctypes.c_void_p, CB, ctypes.c_void_p]
    jack.jack_get_sample_rate.argtypes = [ctypes.c_void_p]
    jack.jack_activate.argtypes = [ctypes.c_void_p]
    jack.jack_connect.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    jack.jack_deactivate.argtypes = [ctypes.c_void_p]
    jack.jack_client_close.argtypes = [ctypes.c_void_p]
    jack.jack_get_ports.restype = ctypes.POINTER(ctypes.c_char_p)
    jack.jack_get_ports.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong]
    jack.jack_free.argtypes = [ctypes.c_void_p]

    c = jack.jack_client_open(b"own-host-probe", 0, None)
    if not c:
        sys.exit("own_host_lv2_probe: cannot open a JACK client (is jackd running?)")
    audio = b"32 bit float mono audio"
    outs = [jack.jack_port_register(c, b"out_%d" % i, audio, PORT_IS_OUTPUT, 0) for i in (1, 2)]
    ins = [jack.jack_port_register(c, b"in_%d" % i, audio, PORT_IS_INPUT, 0) for i in (1, 2)]
    rate = jack.jack_get_sample_rate(c)
    state = {"phase": 0, "measuring": False, "in_peak": 0.0, "out_peak": [0.0, 0.0], "cycles": 0}
    step = 2.0 * math.pi * HZ / rate

    def process(n, _arg):
        sig = []
        for k in range(n):
            sig.append(AMPLITUDE * math.sin(state["phase"]))
            state["phase"] = (state["phase"] + step) % (2.0 * math.pi)
        for p in outs:
            (ctypes.c_float * n).from_address(jack.jack_port_get_buffer(p, n))[:] = sig
        if state["measuring"]:
            state["cycles"] += 1
            state["in_peak"] = max(state["in_peak"], max(abs(x) for x in sig))
            for i, p in enumerate(ins):
                buf = (ctypes.c_float * n).from_address(jack.jack_port_get_buffer(p, n))
                state["out_peak"][i] = max(state["out_peak"][i], max(abs(x) for x in buf))
        return 0

    cb = CB(process)
    jack.jack_set_process_callback(c, cb, None)
    if jack.jack_activate(c) != 0:
        sys.exit("own_host_lv2_probe: cannot activate the JACK client")
    try:
        t_in, t_out = published(jack, c, target)
        n = min(len(t_in), len(t_out), 2)
        for i in range(n):
            for a, b in (("own-host-probe:out_%d" % (i + 1), t_in[i]), (t_out[i], "own-host-probe:in_%d" % (i + 1))):
                if jack.jack_connect(c, a.encode(), b.encode()) != 0:
                    sys.exit("own_host_lv2_probe: cannot connect %s to %s" % (a, b))
        time.sleep(SETTLE_S)
        state["measuring"] = True
        time.sleep(MEASURE_S)
        state["measuring"] = False
        if state["cycles"] == 0:
            sys.exit("own_host_lv2_probe: JACK ran no process cycle")
        # the tolerance: float32 and the plugin's own smoothing leave the measured gain within about 0.005 of the set one
        # (1.9953 measured), while the nearest wrong value, an unprocessed signal, measures 1.0 and silence 0.0
        ratios = [p / state["in_peak"] for p in state["out_peak"][:n]]
        print("own_host_lv2_probe: %s in peak %.4f, out peak %s, gain %s (wanted %.4f +- %.4f)"
              % (target, state["in_peak"], ["%.4f" % p for p in state["out_peak"][:n]], ["%.4f" % r for r in ratios], want, tol))
        if any(abs(r - want) > tol for r in ratios):
            sys.exit("own_host_lv2_probe: the output does not carry the gain the plugin was set to")
    finally:
        # the interpreter must not tear down while libjack's RT thread can still fire the ctypes
        # callback (plugin-hostd#110): close the client on every exit path that follows activate
        jack.jack_deactivate(c)
        jack.jack_client_close(c)


main()
