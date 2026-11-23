# SPDX-License-Identifier: GPL-3.0-or-later
# What describe writes is read by omx-contract's own loader. The `$schema` of a descriptor is the one address the
# loader accepts, https://openmixer.org/schema/omx-contract/v3/omx-contract.schema.json with the major only in the
# path (omx-contract#106): a literal here, never the constant of src/describe.c, so a moved address is a red test.
# Each recorded dump's descriptor is also put in a contract directory and read by loadContractDir, when
# OMX_CONTRACT_LOADER names omx-contract's built contract-dir.mjs.
# A scanned descriptor is never installed, so the copy the loader reads says origin "authored": the loader must get
# past its `$schema` check, and any refusal it gives must be another one.
#   describe_loader_test.py   PROBE is the runner (default ./plugin-hostd-probe)
import hashlib, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe"))
FIELDS = os.path.join(ROOT, "tests", "fixtures", "fields")
CONTRACT_DIR = os.path.join(ROOT, "tests", "fixtures", "contract-dir")
LOADER = os.environ.get("OMX_CONTRACT_LOADER")
SCHEMA = "https://openmixer.org/schema/omx-contract/v3/omx-contract.schema.json"
CASES = {"clap-controls": "clap:controls.clap#org.freemixer.plugin-qualify.fixture.controls",
         "lv2-compressor": "lv2:urn:example:compressor", "lv2-eq": "lv2:urn:example:eq"}
failed = 0
for name, target in CASES.items():
    r = subprocess.run([PROBE, "describe", "--table", os.path.join(ROOT, "data", "formats", target.split(":")[0] + ".json"),
                        "--fields-from", os.path.join(FIELDS, name + ".tsv"), "--contract-dir", CONTRACT_DIR, target],
                       capture_output=True, text=True)
    doc = json.loads(r.stdout)
    ok = doc.get("$schema") == SCHEMA
    print(("ok   " if ok else "FAIL ") + "%s: describe writes the address the loader accepts (%s)" % (name, doc.get("$schema")))
    failed += not ok
    if not LOADER:
        continue
    with tempfile.TemporaryDirectory() as tmp:
        pkg = os.path.join(tmp, "3", "plugin-hostd-describe")
        os.makedirs(pkg)
        body = json.dumps(dict(doc, origin="authored"), indent=2)
        open(os.path.join(pkg, "d.json"), "w").write(body)
        open(os.path.join(pkg, "MANIFEST.json"), "w").write(json.dumps({
            "package": "plugin-hostd-describe", "version": "0.0.0", "schemaMajor": 3,
            "files": {"d.json": hashlib.sha256(body.encode()).hexdigest()}}))
        js = "import(process.argv[1]).then(m=>{try{m.loadContractDir({dir:process.argv[2],env:{}});console.log('loaded')}" \
             "catch(e){console.log(e.code+': '+e.message)}})"
        out = subprocess.run(["node", "-e", js, LOADER, tmp], capture_output=True, text=True).stdout.strip()
        ok = "schema.major" not in out
        print(("ok   " if ok else "FAIL ") + "%s: loadContractDir: %s" % (name, out[:300]))
        failed += not ok
sys.exit(1 if failed else 0)
