#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The history keys are the domain plugin-hostd/history (contract.d/plugin-hostd/history/history.json), the call-level
# test of the sorting pass row V18:
#   a. golden: history_line, the daemon's real writer of a history record (compiled against the committed vocabulary
#      header), writes the 15 keys frozen from data/history.json at 2235c68, in that order, and the domain holds them
#   b. the committed include/plugin-hostd/plugin_hostd_vocabulary.h is the domains' render byte for byte, and
#      data/history.json is gone
#   c. sabotage: a scratch domain with pss_mb_solo renamed pss_x renders a header whose history_line writes pss_x=, and
#      with PLUGIN_HOSTD_HISTORY_KEYS removed the history does not build
# Environment: as tests/domain_render.py, and CC, CFLAGS (with the include flags) and LIBS (make test-history-domain).
import json
import os
import shutil
import subprocess
import sys
import tempfile

from domain_render import ROOT, env, render, scratch_include

DOMAIN = os.path.join(ROOT, "contract.d", "plugin-hostd", "history", "history.json")
HEADER = os.path.join(ROOT, "include", "plugin-hostd", "plugin_hostd_vocabulary.h")
GOLDEN = ["first", "last", "windows_solo", "windows_grouped", "cpu_p95_solo", "cpu_max_solo", "pss_mb_solo",
          "xrun_windows_solo", "xrun_windows_grouped", "crashes_solo", "crashes_grouped", "restarts_grouped",
          "quarantines", "last_crash", "last_crash_grouped"]  # data/history.json at 2235c68
SOURCES = ["history.c", "words.c", "fsutil.c", "writer.c", "machine.c", "domain_words.c"]
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def line_keys(include):
    """The keys history_line writes for an empty record, compiled against the header under <include>/plugin-hostd/."""
    tmp = tempfile.mkdtemp(prefix="history-line-")
    try:
        c = os.path.join(tmp, "line.c")
        with open(c, "w") as f:
            f.write('#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "history.h"\n'
                    'int main(void) { history_rec_t r; memset(&r, 0, sizeof(r)); r.uri = "clap:/x.clap#a"; r.klass = "x86_64/1-2/1GHz";'
                    ' memset(r.digest, \'a\', sizeof(r.digest) - 1); char *l = history_line(&r); fputs(l, stdout); free(l); return 0; }\n')
        exe = os.path.join(tmp, "line")
        cmd = [env("CC", "cc"), "-I" + include] + env("CFLAGS", "").split() + ["-I" + os.path.join(ROOT, "src"), "-o", exe, c] + \
              [os.path.join(ROOT, "src", s) for s in SOURCES] + env("LIBS", "").split()
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            return None, r.stderr[-400:]
        out = subprocess.run([exe], capture_output=True, text=True, check=True).stdout
        return [kv.split("=", 1)[0] for kv in out.split()[4:]], ""
    finally:
        shutil.rmtree(tmp)


with open(DOMAIN, encoding="utf-8") as f:
    doc = json.load(f)

# a
keys, err = line_keys(os.path.join(ROOT, "include"))
check(keys == GOLDEN, "a. history_line writes the 15 golden keys in order: %s %s" % (keys, err))
check([e["const"] for e in doc["components"]["schemas"]["PLUGIN_HOSTD_HISTORY_KEYS"]["oneOf"]] == GOLDEN,
      "a. the domain holds the 15 keys in order")

# b
out = tempfile.mkdtemp(prefix="history-out-")
rc, msg = render(os.path.join(ROOT, "contract.d"), out)
got = open(os.path.join(out, "plugin_hostd_vocabulary.h"), "rb").read() if rc == 0 else b""
check(rc == 0 and got == open(HEADER, "rb").read(), "b. the committed vocabulary header is the domains' render, byte for byte %s" % ("" if rc == 0 else msg))
check(not os.path.exists(os.path.join(ROOT, "data", "history.json")), "b. data/history.json, the old source, is gone")
shutil.rmtree(out)

# c
scratch = tempfile.mkdtemp(prefix="history-sabotage-")
inc = scratch_include()
try:
    cd = os.path.join(scratch, "contract.d")
    shutil.copytree(os.path.join(ROOT, "contract.d"), cd)
    sab = json.loads(json.dumps(doc))
    for e in sab["components"]["schemas"]["PLUGIN_HOSTD_HISTORY_KEYS"]["oneOf"]:
        if e["const"] == "pss_mb_solo":
            e["const"] = "pss_x"
    with open(os.path.join(cd, "plugin-hostd", "history", "history.json"), "w") as f:
        json.dump(sab, f, indent=2)
    rc, msg = render(cd, os.path.join(inc, "plugin-hostd"))
    keys, err = line_keys(inc) if rc == 0 else (None, msg)
    check(keys is not None and keys[6] == "pss_x", "c. a renamed key in a scratch domain is history_line's: %s %s" % (keys and keys[6], err))
    del sab["components"]["schemas"]["PLUGIN_HOSTD_HISTORY_KEYS"]
    with open(os.path.join(cd, "plugin-hostd", "history", "history.json"), "w") as f:
        json.dump(sab, f, indent=2)
    rc, msg = render(cd, os.path.join(inc, "plugin-hostd"))
    keys, err = line_keys(inc) if rc == 0 else (None, msg)
    check(keys is None, "c. without PLUGIN_HOSTD_HISTORY_KEYS in a scratch domain the history does not build: %s" % (keys or "refused"))
finally:
    shutil.rmtree(scratch)
    shutil.rmtree(inc)

print("history domain: %s" % ("ok" if not fails else "FAILED (%d)" % fails))
sys.exit(1 if fails else 0)
