# SPDX-License-Identifier: GPL-3.0-or-later
# A preset an instance saved loads back into that instance after a patch of the plugin's own changed its parameters'
# names (#27), with a real omx-clap-host behind the daemon, over jack, in the namespace tests/jack_e2e.sh built. The
# plugin is Surge XT as the distribution packages it (clap-surge-xt, surge-xt-data): its parameter ids are hashes and
# the names of its macros and FX slots follow the loaded patch.
import json, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Daemon, check, run_tests, wait_for

EXE = os.environ["PLUGIN_HOSTD"]
CLAP_HOST = os.environ["OMX_CLAP_HOST"]
SURGE = os.environ["SURGE_CLAP"]             # Surge_XT.clap
SURGE_ID = "org.surge-synth-team.surge-xt"
PATCH = os.environ["SURGE_FACTORY_PATCH"]    # a factory patch of surge-xt-data, an .fxp
PROBE = os.environ.get("PLUGIN_HOSTD_PROBE") or os.path.join(os.path.dirname(EXE), "plugin-hostd-probe")
TESTS = []
INST = 3


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


def param_ids(count):
    """the first `count` automatable 0..1 travels of the plugin outside its macros (a patch need not move a macro), as
    the scan names them: their CLAP ids in decimal"""
    scan = json.loads(subprocess.run([PROBE, "describe", "clap:%s#%s" % (SURGE, SURGE_ID)], capture_output=True,
                                     text=True, timeout=120, check=True).stdout)
    travels = [c for c in scan["controls"] if c.get("kind") == "travel" and c.get("automatable")
               and c["travel"]["min"] == 0 and c["travel"]["max"] == 1 and c.get("group") != ["Macros"]]
    return [str(c["id"]) for c in travels[:count]]


def worker_code(key):
    """a reply code omx-clap-host declares, from omx-clap-core's verbs.json in the contract directory"""
    contractdir = subprocess.run([os.environ.get("PKG_CONFIG", "pkg-config"), "--variable=contractdir", "omx-contract"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    with open(os.path.join(contractdir, "3", "omx-clap-core", "verbs.json")) as f:
        return "resp %d" % json.load(f)["HOST_REPLY_CODES"]["codes"][key]["resp"]


def value(d, inst, pid):
    r = d.ok("param_get %d %s" % (inst, pid))
    return float(r.split()[2])


@test
def saved_preset_loads_back_after_a_factory_patch():
    d = Daemon(EXE, CLAP_HOST, clap_worker=CLAP_HOST)
    try:
        d.expect("add clap:%s#%s %d" % (SURGE, SURGE_ID, INST), "resp %d" % INST)
        d.wait_up(INST)
        ids = param_ids(4)
        check(len(ids) == 4, "four parameters to set (the scan gave %r)" % ids)
        wanted = {pid: 0.125 + 0.25 * n for n, pid in enumerate(ids)}
        for pid, v in wanted.items():
            d.expect("param_set %d %s %.6f" % (INST, pid, v), "resp 0")
        path = os.path.join(tempfile.mkdtemp(prefix="plugin-hostd-27."), "surge-xt.json")
        d.expect('preset_save %d %s "plugin-hostd 27"' % (INST, path), "resp 0")
        d.expect("preset_load %d file:%s#" % (INST, PATCH), "resp 0")
        # a CLAP preset load answers at once and applies on the plugin's main thread a moment later
        wait_for(lambda: any(abs(value(d, INST, pid) - v) > 1e-4 for pid, v in wanted.items()), "the factory patch to move a value", 10)
        # param_get takes a parameter's CLAP id; Surge XT's are hashes, so 0 names no parameter of it
        d.expect("param_get %d 0" % INST, worker_code("paramSymbolInvalid"))
        d.expect("preset_load %d %s" % (INST, path), "resp 0")
        restored = lambda: all(abs(value(d, INST, pid) - v) < 1e-4 for pid, v in wanted.items())
        wait_for(restored, "the saved values back: %r, reading %r" % (wanted, {pid: value(d, INST, pid) for pid in ids}), 10)
    finally:
        d.close()


sys.exit(run_tests(TESTS))
