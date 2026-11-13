# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-hostd-probe describe --pages (docs/formats.md#the-pages-describe-pages-writes): the descriptor's controls,
# each on exactly one page of its group's run, in declared order, cut at 8. A plugin with several hundred parameters
# and no groups of its own still gets pages, in declared order, the same on every run (plugin-hostd#7: Surge XT's
# own groups already reach the descriptor, by clap-controls.tsv and lv2-eq.tsv below; this covers the plugin that
# groups nothing of its own, which a hand-picked fixture does not reach at hundreds of parameters).
#   describe_pages_test.py   PROBE is the runner (default ./plugin-hostd-probe)
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe"))
FIELDS = os.path.join(ROOT, "tests", "fixtures", "fields")
TABLES = os.path.join(ROOT, "data", "formats")
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def describe_pages(target, dump):
    fmt = target.split(":", 1)[0]
    cmd = [PROBE, "describe", "--pages", "--table", os.path.join(TABLES, fmt + ".json"), "--fields-from", dump, target]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def scratch(tmp, name, text):
    path = os.path.join(tmp, name)
    with open(path, "w") as f:
        f.write(text)
    return path


def many_params_tsv(n):
    """a CLAP plugin of n parameters, none in a module of its own"""
    lines = ["# omx-clap-scan --fields 1", "plugin\tclap_entry\tmany.clap",
             "plugin\tclap_plugin_descriptor.id\torg.freemixer.plugin-qualify.fixture.many",
             "plugin\tclap_plugin_descriptor.name\tmany"]
    for i in range(n):
        lines.append("param:%d\tclap_param_info.id\t%d" % (i, 1000 + i))
        lines.append("param:%d\tclap_param_info.name\tp%d" % (i, i))
        lines.append("param:%d\tclap_param_info.min_value\t0" % i)
        lines.append("param:%d\tclap_param_info.max_value\t1" % i)
        lines.append("param:%d\tclap_param_info.default_value\t0" % i)
    return "\n".join(lines) + "\n"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        n = 300
        target = "clap:many.clap#org.freemixer.plugin-qualify.fixture.many"
        dump = scratch(tmp, "many.tsv", many_params_tsv(n))
        r1 = describe_pages(target, dump)
        r2 = describe_pages(target, dump)
        check(r1.returncode == 0, "%d ungrouped params: describe --pages exits 0 (%s)" % (n, r1.stderr.strip()))
        doc = json.loads(r1.stdout or "{}")
        pages = doc.get("pages", [])
        ids = [p for page in pages for p in page["params"]]
        check(ids == [1000 + i for i in range(n)], "every parameter in declared order, on exactly one page")
        check(len(ids) == len(set(ids)), "no parameter repeats across pages")
        check(all(page["group"] is None for page in pages),
              "the controls with no group of their own are one group, null")
        sizes = [len(page["params"]) for page in pages]
        check(sizes[:-1] == [8] * (len(sizes) - 1) and 1 <= sizes[-1] <= 8,
              "pages of 8, the last whatever parameters are left (%r)" % sizes)
        check(len(pages) == -(-n // 8), "%d parameters need %d pages of 8" % (n, -(-n // 8)))
        check(r1.stdout == r2.stdout, "the pages are the same on every run")

        # a plugin that does group its own controls: one page per group, in the order the group first appears among
        # the controls, the ungrouped controls their own page (the fixture plugin-hostd#7's ruling already covers:
        # Surge XT's own module paths reach the descriptor's group the same way, docs/formats.md#group-path)
        r = describe_pages("clap:controls.clap#org.freemixer.plugin-qualify.fixture.controls",
                           os.path.join(FIELDS, "clap-controls.tsv"))
        check(r.returncode == 0, "clap-controls: describe --pages exits 0 (%s)" % r.stderr.strip())
        check(json.loads(r.stdout or "{}") == {"pages": [{"group": ["Oscillator"], "params": [3]},
                                                          {"group": ["Filter", "Envelope"], "params": [5]},
                                                          {"group": None, "params": [7]}]},
              "clap-controls: one page per group, the ungrouped control its own (%s)" % r.stdout.strip())

        # an LV2 plugin whose ports carry groups (docs/formats.md#port-group): the same, by lv2 symbol
        r = describe_pages("lv2:urn:example:eq", os.path.join(FIELDS, "lv2-eq.tsv"))
        check(r.returncode == 0, "lv2-eq: describe --pages exits 0 (%s)" % r.stderr.strip())
        check(json.loads(r.stdout or "{}") == {"pages": [{"group": ["Bands", "Band 1"], "params": ["b1_freq"]},
                                                          {"group": ["Bands", "Band 2"], "params": ["b2_freq"]},
                                                          {"group": ["Master"], "params": ["trim"]}]},
              "lv2-eq: one page per group, by declared order (%s)" % r.stdout.strip())

        # describe --pages refuses exactly as describe does: the same table, the same dump, read once
        r = describe_pages("lv2:urn:example:eq", scratch(tmp, "bad.tsv", "# omx-clap-scan --fields 2\n"))
        check(r.returncode == 2 and "# omx-clap-scan --fields 1" in r.stderr and not r.stdout,
              "describe --pages refuses as describe refuses (%d: %s)" % (r.returncode, r.stderr.strip()))
    if failed:
        print("describe-pages: %d failed" % failed)
        sys.exit(1)
    print("describe-pages: ok")


if __name__ == "__main__":
    main()
