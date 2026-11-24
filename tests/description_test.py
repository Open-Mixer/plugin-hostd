# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""plugin-hostd and the descriptions store (omx-panel docs/descriptions-store.md, section 7; lane 9, plugin-hostd#210).

Over the wire, against workers that are no plugin hosts (tests/fake-host), with a store of each test's own
(tests/desc_store_fixture.py) and stand-ins on PATH for the programs the ask runs: each logs its arguments, its nice,
its scheduling policy and its I/O priority class, and the stand-in omx-panel puts an entry with the store's own command.

- groups from the store, else declared: an LV2 plugin with no pg:group pages by the store's groups, and by its declared
  ones when no layer holds it or no store is installed; plugin-hostd infers none;
- description_get <uri>: resp 0 <sha256> <format> <uri> <layer>, -529 when no layer holds the plugin, -530 while its
  ask runs;
- the ask, for a plugin no layer holds: plugin-qualify-sync --plugin, then omx-panel describe --plugin ... --store, then
  the three generators with that plugin's --only, each once, at the lowest priority, for that plugin only; none for a
  known key, none with add ... no-ask, none when plugin-qualify-sync is absent; description_changed <uri> when it ends.
"""
import glob, os, shutil, stat, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from desc_store_fixture import Store, have_command
from harness import Daemon, check, resp, run_tests, wait_for
from scan_fixture import sha, write

EXE = os.path.abspath(os.environ.get("PLUGIN_HOSTD", "./tests/plugin-hostd-test"))
FAKE = os.path.abspath(os.environ.get("FAKE_HOST", "tests/fake-host"))
TESTS = []

UNGROUPED = "urn:openmixer:test:ungrouped"
CLAP_ID = "org.openmixer.test.described"
MANIFEST = """@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<%s> a lv2:Plugin ; lv2:binary <ungrouped.so> ; rdfs:seeAlso <ungrouped.ttl> .
"""
# four control inputs in no pg:group, an output and a notOnGUI port: today one page "Controls"
PORTS = """@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
@prefix pprops: <http://lv2plug.in/ns/ext/port-props#> .
<%s> a lv2:Plugin , lv2:EQPlugin ;
    lv2:port [ a lv2:AudioPort , lv2:InputPort ; lv2:index 0 ; lv2:symbol "in" ; lv2:name "In" ] ,
             [ a lv2:AudioPort , lv2:OutputPort ; lv2:index 1 ; lv2:symbol "out" ; lv2:name "Out" ] ,
             [ a lv2:ControlPort , lv2:InputPort ; lv2:index 2 ; lv2:symbol "gain1" ; lv2:name "Gain 1" ;
               lv2:default 0 ; lv2:minimum -12 ; lv2:maximum 12 ] ,
             [ a lv2:ControlPort , lv2:InputPort ; lv2:index 3 ; lv2:symbol "freq1" ; lv2:name "Freq 1" ;
               lv2:default 100 ; lv2:minimum 20 ; lv2:maximum 20000 ] ,
             [ a lv2:ControlPort , lv2:InputPort ; lv2:index 4 ; lv2:symbol "gain2" ; lv2:name "Gain 2" ;
               lv2:default 0 ; lv2:minimum -12 ; lv2:maximum 12 ] ,
             [ a lv2:ControlPort , lv2:InputPort ; lv2:index 5 ; lv2:symbol "freq2" ; lv2:name "Freq 2" ;
               lv2:default 1000 ; lv2:minimum 20 ; lv2:maximum 20000 ] ,
             [ a lv2:ControlPort , lv2:InputPort ; lv2:index 6 ; lv2:symbol "hidden" ; lv2:name "Hidden" ;
               lv2:portProperty pprops:notOnGUI ; lv2:default 0 ; lv2:minimum 0 ; lv2:maximum 1 ] ,
             [ a lv2:ControlPort , lv2:OutputPort ; lv2:index 7 ; lv2:symbol "meter" ; lv2:name "Meter" ;
               lv2:default 0 ; lv2:minimum 0 ; lv2:maximum 1 ] .
"""
STORE_GROUPS = [("band1", "Band 1", ["gain1", "freq1"]), ("band2", "Band 2", ["gain2", "freq2"])]
DECLARED_PAGES = ['resp 0 0 "" "Controls" gain1 freq1 gain2 freq2 - - - -']
STORE_PAGES = ['resp 0 0 "" "Band 1" gain1 freq1 - - - - - -', 'resp 0 1 "" "Band 2" gain2 freq2 - - - - - -']

# the probe the add's scan runs: a descriptor and a panel of its own, so no installed table is read
SCANNER = """#!/bin/sh
if [ "$1" = panel ]; then printf '{"plugin":{"id":"x","version":"1"},"panel":{}}'; exit 0; fi
echo "$2" >> "$SCAN_LOG"
printf '{"plugin":{"id":"%s","version":"1"},"controls":[]}' "$2"
"""
# each program of the ask: its name, its arguments, its nice, its policy and its I/O class, one line per run.
# /proc/self/stat field 19 is the nice, field 41 the policy (5 is SCHED_IDLE); ionice -p prints the class
STANDIN = """#!/bin/sh
nice=$(cut -d' ' -f19 /proc/$$/stat); policy=$(cut -d' ' -f41 /proc/$$/stat)
io=$(ionice -p $$ 2>/dev/null | cut -d: -f1)
echo "%(name)s $* nice=$nice policy=$policy io=$io" >> "$ASK_LOG"
if [ -n "$ASK_HOLD" ] && [ "%(name)s" = plugin-qualify-sync ]; then while [ ! -e "$ASK_HOLD" ]; do sleep 0.02; done; fi
%(extra)s
exit 0
"""
# the stand-in omx-panel describe --plugin <target> --descriptor <file> --sha256 <hex> --store: puts the entry of the
# key, as the real one does, through the store's own command
DESCRIBE = """
if [ "$1" = describe ]; then
  python3 - "$@" <<'EOF'
import os, sys
sys.path.insert(0, os.environ["DESC_FIXTURE_DIR"])
from desc_store_fixture import Store
a = sys.argv[1:]
target, sha = a[a.index("--plugin") + 1], a[a.index("--sha256") + 1]
s = Store.__new__(Store)
s.dir = os.environ["DESC_STORE_DIR"]
s.base, s.system, s.user = (os.path.join(s.dir, n + ".sqlite") for n in ("base", "system", "user"))
import desc_store_fixture as f
s.rules = int(f.run(["rules"])[1])
if target.startswith("lv2:"):
    fmt, uri, path = "lv2", target[4:], os.environ["DESC_BUNDLE"]
else:
    fmt, uri, path = "clap", target.split("#", 1)[1], a[a.index("--descriptor") + 1]
s.put(sha, fmt, uri, s.source(fmt, path), groups=eval(os.environ.get("DESC_GROUPS", "None")))
EOF
fi
"""
PROGRAMS = ("plugin-qualify-sync", "omx-panel", "omx-complement-sync", "omx-modgui-sync", "omx-lv2ui-sync")


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


class World:
    """an LV2 bundle with no pg:group, a CLAP file, a scanner, a store, and the ask's stand-ins in a bin directory"""

    def __init__(self, base=True, programs=PROGRAMS):
        self.dir = tempfile.mkdtemp(prefix="plugin-hostd-describe.")
        self.lv2_dir = os.path.join(self.dir, "lv2")
        self.bundle = os.path.join(self.lv2_dir, "ungrouped.lv2")
        os.makedirs(self.bundle)
        write(os.path.join(self.bundle, "manifest.ttl"), (MANIFEST % UNGROUPED).encode())
        write(os.path.join(self.bundle, "ungrouped.ttl"), (PORTS % UNGROUPED).encode())
        self.lv2_binary = os.path.join(self.bundle, "ungrouped.so")
        write(self.lv2_binary, b"an lv2 build")
        self.clap = os.path.join(self.dir, "clap", "described.clap")
        os.makedirs(os.path.dirname(self.clap))
        write(self.clap, b"a clap build")
        self.clap_uri = "clap:%s#%s" % (self.clap, CLAP_ID)
        self.lv2_uri = "lv2:" + UNGROUPED
        self.scanner = self.exe("scanner", SCANNER)
        self.descriptors = os.path.join(self.dir, "descriptors")
        self.bin = os.path.join(self.dir, "bin")
        os.makedirs(self.bin)
        for name in programs:
            self.exe(os.path.join("bin", name), STANDIN % {"name": name, "extra": DESCRIBE if name == "omx-panel" else ""})
        self.ask_log = os.path.join(self.dir, "ask.log")
        self.scan_log = os.path.join(self.dir, "scans.log")
        self.store = Store(base=base)

    def exe(self, name, text):
        path = os.path.join(self.dir, name)
        write(path, text.encode())
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return path

    def daemon(self, conf=None, env=None):
        c = {"probe": self.scanner, "lv2_path": self.lv2_dir, "descriptor_dir": self.descriptors, "clap_path": os.path.dirname(self.clap)}
        c.update(conf or {})
        e = {"PATH": self.bin + ":" + os.environ.get("PATH", ""), "ASK_LOG": self.ask_log, "SCAN_LOG": self.scan_log,
             "DESC_STORE_DIR": self.store.dir, "DESC_BUNDLE": self.bundle, "DESC_GROUPS": repr(STORE_GROUPS),
             "DESC_FIXTURE_DIR": os.path.dirname(os.path.abspath(__file__))}
        e.update(self.store.daemon_env())
        e.update(env or {})
        return Daemon(EXE, FAKE, conf=c, env=e)

    def asked(self):
        if not os.path.exists(self.ask_log):
            return []
        with open(self.ask_log) as f:
            return [l.strip() for l in f if l.strip()]

    def descriptor(self):
        found = glob.glob(os.path.join(self.descriptors, "*.json"))
        return found[0] if found else None

    def put_lv2(self, groups=STORE_GROUPS):
        self.store.put(sha(self.lv2_binary), "lv2", UNGROUPED, self.store.source("lv2", self.bundle), groups)

    def close(self):
        self.store.close()
        shutil.rmtree(self.dir, ignore_errors=True)


def pages(d, n):
    return [d.send("remote_page_get %d %d" % (n, k)) for k in range(int(d.send("remote_pages %d" % n).split()[1]))]


# ---------------------------------------------------------------- groups from the store, else declared

@test
def an_lv2_plugin_with_no_pg_group_pages_by_the_groups_its_store_entry_holds():
    """plugin-hostd#179 through the store: the store's grouped verdict replaces the declared groups for the pages; with
    the entry removed the plugin pages by its declared ones again (one page, Controls). plugin-hostd infers nothing"""
    w = World()
    try:
        w.put_lv2()
        d = w.daemon(conf={}, env={"PATH": "/usr/bin:/bin"})
        try:
            d.expect("add %s 0 no-ask" % w.lv2_uri, "resp 0")
            check(pages(d, 0) == STORE_PAGES, "the store's groups page the plugin: %s" % pages(d, 0))
        finally:
            d.close()
        w.store.remove(sha(w.lv2_binary), "lv2", UNGROUPED)
        d = w.daemon(env={"PATH": "/usr/bin:/bin"})
        try:
            d.expect("add %s 0 no-ask" % w.lv2_uri, "resp 0")
            check(pages(d, 0) == DECLARED_PAGES, "with no entry the declared groups: %s" % pages(d, 0))
        finally:
            d.close()
    finally:
        w.close()


@test
def with_no_store_installed_the_add_pages_by_the_declared_groups_and_description_get_is_529():
    w = World(base=False)
    try:
        w.put_lv2()     # a layer above no base: a store whose base is absent is no store
        d = w.daemon(env={"PATH": "/usr/bin:/bin"})
        try:
            d.expect("add %s 0" % w.lv2_uri, "resp 0")
            check(pages(d, 0) == DECLARED_PAGES, "no store: the declared groups: %s" % pages(d, 0))
            d.expect("description_get %s" % w.lv2_uri, resp("DESCRIPTOR_ABSENT"))
        finally:
            d.close()
    finally:
        w.close()


@test
def a_changed_ttl_stales_the_entry_and_the_plugin_pages_by_its_declared_groups():
    """the entry's source is the bundle's TTL as installed (3.6): an edit of the TTL over the same binary makes it stale"""
    w = World()
    try:
        w.put_lv2()
        with open(os.path.join(w.bundle, "ungrouped.ttl"), "a") as f:
            f.write("# an edit\n")
        d = w.daemon(env={"PATH": "/usr/bin:/bin"})
        try:
            d.expect("add %s 0" % w.lv2_uri, "resp 0")
            check(pages(d, 0) == DECLARED_PAGES, "a stale entry is absent: %s" % pages(d, 0))
            d.expect("description_get %s" % w.lv2_uri, resp("DESCRIPTOR_ABSENT"))
        finally:
            d.close()
    finally:
        w.close()


# ---------------------------------------------------------------- description_get

@test
def description_get_answers_the_key_and_the_layer_that_holds_it():
    w = World()
    try:
        d = w.daemon(env={"PATH": "/usr/bin:/bin"})
        try:
            d.expect("description_get %s" % w.lv2_uri, resp("DESCRIPTOR_ABSENT"))
            d.expect("description_get clap:/nonexistent.clap#x", resp("DESCRIPTOR_ABSENT"))
            d.expect("description_get", "resp -902")
            d.expect("description_get a b", "resp -902")
            w.put_lv2()
            d.expect("description_get %s" % w.lv2_uri,
                     "resp 0 %s lv2 %s %s" % (sha(w.lv2_binary), UNGROUPED, w.store.layer()))
            # a CLAP plugin's source is the descriptor its scan wrote: no descriptor, no key it can be read by
            d.expect("add %s 1 no-ask" % w.clap_uri, "resp 1")
            wait_for(lambda: w.descriptor() is not None, "the scan writes the CLAP descriptor")
            d.expect("description_get %s" % w.clap_uri, resp("DESCRIPTOR_ABSENT"))
            w.store.put(sha(w.clap), "clap", CLAP_ID, w.store.source("clap", w.descriptor()))
            wait_for(lambda: d.send("description_get %s" % w.clap_uri) ==
                     "resp 0 %s clap %s %s" % (sha(w.clap), CLAP_ID, w.store.layer()), "description_get of the CLAP key")
        finally:
            d.close()
    finally:
        w.close()


# ---------------------------------------------------------------- the ask

def runs(w, name):
    return [l for l in w.asked() if l.split(" ", 1)[0] == name]


@test
def an_unknown_plugin_is_asked_for_once_at_the_lowest_priority_and_description_changed_tells_the_clients():
    w = World()
    hold = os.path.join(w.dir, "go")
    try:
        d = w.daemon(env={"ASK_HOLD": hold})
        try:
            d.expect("add %s 0" % w.lv2_uri, "resp 0")
            check(pages(d, 0) == DECLARED_PAGES, "meanwhile the plugin pages as today: %s" % pages(d, 0))
            wait_for(lambda: runs(w, "plugin-qualify-sync"), "the ask runs plugin-qualify-sync")
            d.expect("description_get %s" % w.lv2_uri, resp("DESCRIPTOR_PENDING"))
            d.expect("add %s 1" % w.lv2_uri, "resp 1")
            mark = d.mark()
            write(hold, b"")
            d.wait_event("description_changed %s" % w.lv2_uri, since=mark)
            d.expect("description_get %s" % w.lv2_uri,
                     "resp 0 %s lv2 %s %s" % (sha(w.lv2_binary), UNGROUPED, w.store.layer()))
            check(pages(d, 0) == STORE_PAGES and pages(d, 1) == STORE_PAGES,
                  "the next remote_pages answer from the entry: %s" % pages(d, 1))
            target = w.lv2_uri
            system = " --system" if os.geteuid() == 0 else ""
            want = ["plugin-qualify-sync --plugin %s --under-load%s" % (target, system),
                    "omx-panel describe --plugin %s --descriptor %s --sha256 %s --store" % (target, w.descriptor(), sha(w.lv2_binary)),
                    "omx-complement-sync --only ungrouped.lv2",
                    "omx-modgui-sync --only ungrouped.lv2",
                    "omx-lv2ui-sync --only ungrouped.lv2"]
            got = [l.split(" nice=")[0] for l in w.asked()]
            check(got == want, "each once, in order, for that plugin only:\n  %s\nwanted\n  %s" % ("\n  ".join(got), "\n  ".join(want)))
            check(all(l.endswith("nice=19 policy=5 io=idle") for l in w.asked()),
                  "nice 19, SCHED_IDLE, the idle I/O class: %s" % w.asked())
            # a known key asks nothing; a second plugin is never asked for by the first one's ask
            d.expect("add %s 2" % w.lv2_uri, "resp 2")
            time.sleep(0.3)
            check(len(w.asked()) == 5, "a known key runs none: %s" % w.asked())
        finally:
            d.close()
    finally:
        w.close()


@test
def a_clap_plugin_is_asked_for_with_the_descriptor_its_scan_wrote_and_no_generator():
    """the generators are LV2's (a MOD GUI, a complement and a desktop UI are LV2 bundles): a CLAP plugin has none"""
    w = World()
    try:
        d = w.daemon()
        try:
            mark = d.mark()
            d.expect("add %s 0" % w.clap_uri, "resp 0")
            d.wait_event("description_changed %s" % w.clap_uri, since=mark)
            target = "clap:%s#%s" % (w.clap, CLAP_ID)
            got = [l.split(" nice=")[0].split(" --under-load")[0] for l in w.asked()]
            want = ["plugin-qualify-sync --plugin %s" % target,
                    "omx-panel describe --plugin %s --descriptor %s --sha256 %s --store" % (target, w.descriptor(), sha(w.clap))]
            check(got == want, "qualify and describe of that plugin, no generator: %s" % got)
            d.expect("description_get %s" % w.clap_uri, "resp 0 %s clap %s %s" % (sha(w.clap), CLAP_ID, w.store.layer()))
        finally:
            d.close()
    finally:
        w.close()


@test
def no_ask_asks_nothing_and_ask_asks_and_a_second_plugin_is_not_asked_for_by_the_first():
    w = World()
    try:
        d = w.daemon()
        try:
            d.expect("add %s 0 no-ask" % w.lv2_uri, "resp 0")
            d.expect("add %s 1 own no-ask" % w.clap_uri, "resp 1")
            time.sleep(0.5)
            check(w.asked() == [], "add ... no-ask runs none: %s" % w.asked())
            d.expect("description_get %s" % w.lv2_uri, resp("DESCRIPTOR_ABSENT"))
            mark = d.mark()
            d.expect("add %s 2 own client ask" % w.lv2_uri, "resp 2")
            d.wait_event("description_changed %s" % w.lv2_uri, since=mark)
            check(len(runs(w, "plugin-qualify-sync")) == 1 and all(w.lv2_uri in l for l in runs(w, "plugin-qualify-sync")),
                  "add ... ask runs them for that plugin only: %s" % w.asked())
        finally:
            d.close()
    finally:
        w.close()


@test
def with_plugin_qualify_sync_absent_no_child_runs_and_the_add_answers_as_before():
    w = World(programs=[p for p in PROGRAMS if p != "plugin-qualify-sync"])
    try:
        d = w.daemon()
        try:
            d.expect("add %s 0" % w.lv2_uri, "resp 0")
            d.expect("add %s 1 ask" % w.lv2_uri, "resp 1")
            d.expect("add %s 2 ask" % w.lv2_uri, "resp 2")
            time.sleep(0.5)
            check(w.asked() == [], "no child runs: %s" % w.asked())
            check(pages(d, 0) == DECLARED_PAGES, "the plugin loads as today: %s" % pages(d, 0))
            d.expect("description_get %s" % w.lv2_uri, resp("DESCRIPTOR_ABSENT"))
            said = d.log().count("plugin-qualify-sync is not installed")
            check(said == 1, "a forced ask logs the reason once: %d times\n%s" % (said, d.log()[-600:]))
        finally:
            d.close()
    finally:
        w.close()


@test
def with_omx_panel_absent_the_describe_step_is_skipped_and_nothing_changes():
    w = World(programs=["plugin-qualify-sync"])
    try:
        d = w.daemon()
        try:
            d.expect("add %s 0" % w.lv2_uri, "resp 0")
            wait_for(lambda: runs(w, "plugin-qualify-sync"), "plugin-qualify-sync runs")
            wait_for(lambda: d.send("description_get %s" % w.lv2_uri) == resp("DESCRIPTOR_ABSENT"), "the ask ends")
            time.sleep(0.3)
            check([l.split(" ", 1)[0] for l in w.asked()] == ["plugin-qualify-sync"], "only qualify ran: %s" % w.asked())
            check(not [e for e in d.events if e.startswith("description_changed")], "no entry, no event: %s" % d.events)
        finally:
            d.close()
    finally:
        w.close()


if __name__ == "__main__":
    if not have_command():
        print("skipping description_test: omx-panel-store is not installed (omx-panel-store, from omx-panel)", file=sys.stderr)
        sys.exit(77 if os.environ.get("DESCRIPTION_TEST_REQUIRED") else 0)
    sys.exit(run_tests(TESTS))
