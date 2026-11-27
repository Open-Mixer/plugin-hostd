# SPDX-License-Identifier: GPL-3.0-or-later
# describe_test.py's omx-contract arm runs only when OMX_CONTRACT_CLI and OMX_CONTRACT_DATA both name something, the
# condition its skip line states (#292): with OMX_CONTRACT_CLI alone it prints the skip and never reaches the arm. A
# stand-in runner answers each recorded case with its recorded descriptor, so no build of the probe is needed.
import os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUB = """#!/usr/bin/env python3
import os, sys
fields = %r
cases = {"clap:controls.clap#org.freemixer.plugin-qualify.fixture.controls": "clap-controls",
         "lv2:urn:example:compressor": "lv2-compressor", "lv2:urn:example:eq": "lv2-eq"}
name = cases.get(sys.argv[-1])
if not name:
    sys.exit(2)
sys.stdout.write(open(os.path.join(fields, name + ".json")).read())
""" % os.path.join(ROOT, "tests", "fixtures", "fields")

with tempfile.TemporaryDirectory() as tmp:
    stub = os.path.join(tmp, "probe")
    with open(stub, "w") as f:
        f.write(STUB)
    os.chmod(stub, 0o755)
    env = {k: v for k, v in os.environ.items() if k != "OMX_CONTRACT_DATA"}
    env.update(PROBE=stub, OMX_CONTRACT_CLI="/bin/false")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "describe_test.py")], env=env,
                       capture_output=True, text=True, timeout=600, cwd=ROOT)
    out = r.stdout + r.stderr
    ok = ("skip omx-contract validate" in r.stdout and "Traceback" not in out
          and "omx-contract validate reads it" not in r.stdout)
    print(("ok   " if ok else "FAIL ") + "OMX_CONTRACT_CLI alone: the skip is printed and the omx-contract arm is not run"
          + ("" if ok else "\n" + "\n".join(out.splitlines()[-6:])))
    sys.exit(0 if ok else 1)
