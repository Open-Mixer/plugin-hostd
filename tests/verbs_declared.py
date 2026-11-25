# SPDX-License-Identifier: GPL-3.0-or-later
# The verbs of the protocol (the domain plugin-hostd-protocol, read from the contract directory through omx-contract's
# rebuild): the daemon's own and the ones both hosts answer, held to the daemon on its socket:
#   - every verb the declarations give plugin-hostd as required or optional answers a well-formed line, one that its
#     declared format takes, with its declared reply (an optional one may refuse with a code it declares), and a
#     malformed line with a code it declares;
#   - the verbs the daemon answers itself are the declared ones and mod-host's: a word of the binary that the daemon
#     answers without relaying it to its worker, and that no declaration and no mod-host command holds, is red;
#   - a verb both hosts owe answers the same line in the same shape from the daemon and from a worker that speaks for
#     omx-clap-host (tests/fake-host, the worker every test of this tree runs), or, where it is optional of a host, a
#     refusal it declares from that host;
#   - one name per number: no refusal number is named by two codes, and each number protocol.h answers is named by a
#     code of the domain plugin-hostd-protocol or of the domain host, whose HOST_REPLY_CODES name the numbers both hosts
#     answer.
# Each word has one home (ruling R5): the verbs both hosts answer (PLUGIN_HOSTD_PROTOCOL_SHARED_VERBS,
# PLUGIN_HOSTD_PROTOCOL_CLAP_HOST_VERBS), HOST_REPLY_CODES, HOST_TRACK_KINDS and HOST_EVENTS are plugin-hostd-protocol's, in
# its domains plugin-hostd-protocol and host; HOSTING_WINDOW_CODES is omx-clap's, in its domain hosting (the one home of its
# hosting codes: omx-clap-core#156). They are read from those domains in the contract directory: the first of
# OMX_CONTRACT_PATH (directories that stand where contractdir stands) that holds each, else pkg-config's contractdir,
# through omx-contract's own rebuild. omx-clap's package 3/omx-clap is read for what is left there: one of these items in
# the package is refused by name, and one its owner's domains do not hold fails by name. Without the package the run
# fails. The run names which source it read. The headers are read as the compiler
# reads them (tests/declared.py): a scratch tree's own copy first, else plugin-hostd-protocol's.
# Usage: verbs_declared.py (PLUGIN_HOSTD, FAKE_HOST, PROTOCOL from the environment, or the tree's own).
import json, os, re, socket, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import declared as protocol_files
import harness  # puts PLUGIN_HOSTD_CLIENT_DIR, when set, on sys.path
import plugin_hostd_client  # the protocol's, python3-plugin-hostd-client
import scan_fixture
from desc_store_fixture import Store
from harness import Daemon, Fail, check, wait_for

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.abspath(os.environ.get("PLUGIN_HOSTD", os.path.join(ROOT, "plugin-hostd")))
FAKE = os.path.abspath(os.environ.get("FAKE_HOST", os.path.join(ROOT, "tests", "fake-host")))
OWN = protocol_files.domain_json()
# the tree whose headers the daemon under test was built against (tests/sabotage.py builds in a scratch tree)
TREE = os.path.dirname(EXE)
HOSTD, CLAP_HOST = "plugin-hostd", "omx-clap-host"
failures = []


def fail(what):
    failures.append(what)
    print("FAIL " + what)


# ---------------------------------------------------------------- the declarations

def codes_of(docs):
    """{ITEM.name: (code, resp)} of every codes item of docs"""
    codes = {}
    for doc in docs:
        for name, item in doc.items():
            if isinstance(item, dict) and item.get("kind") == "codes":
                for key, c in item["codes"].items():
                    codes["%s.%s" % (name, key)] = (c["code"], c.get("resp"))
    return codes


def verbs_of(docs, refs):
    """{word: {format, reply, codes: [resp], implementedBy}} of every verbs item of docs, each code resolved over the
    codes items of refs"""
    codes = codes_of(refs)
    out = {}
    for doc in docs:
        for item in doc.values():
            if isinstance(item, dict) and item.get("kind") == "verbs":
                for v in item["verbs"].values():
                    out[v["verb"]] = dict(v, codes=[codes[c["ref"]][1] for c in v.get("codes", [])])
    return out


def check_one_name(own_docs, shared_docs):
    """one name per number: no resp is named by two codes, of one home or of both, and each number protocol.h's
    PHD_ERRORS answers is named by one code; the domain host owns the numbers both hosts answer and the domain
    plugin-hostd-protocol names only the daemon's own"""
    named = {}
    for pkg, docs in (("plugin-hostd-protocol", own_docs), ("host", shared_docs)):
        for ref, (code, resp) in codes_of(docs).items():
            if resp is not None:
                named.setdefault(resp, []).append("%s %s (%s)" % (pkg, code, ref))
    for resp, names in sorted(named.items()):
        if len(names) > 1:
            fail("%d has %d names: %s" % (resp, len(names), ", ".join(names)))
    header = protocol_files.read_header("protocol.h", TREE)
    # the numbers PHD_ERRORS answers are the rendered OMX_REPLY_*_RESP macros it names; the header defines none of its own
    rendered = {}
    for name in ("plugin_hostd_protocol_vocabulary.h",):
        rendered.update({m: int(n) for m, n in re.findall(r"^#define\s+(OMX_REPLY_\w+_RESP)\s+\((-[0-9]+)\)",
                                                          protocol_files.read_header(name, TREE), re.M)})
    if re.search(r"^#define\s+PHD_ERR_", header, re.M):
        fail("protocol.h defines a PHD_ERR_ number of its own")
    block = header[header.index("#define PHD_ERRORS(X)"):header.index("/* ---------------------------------------------------------------- verbs */")]
    names = re.findall(r"X\([A-Z0-9_]+, (OMX_REPLY_\w+_RESP), ", block)
    absent = [n for n in names if n not in rendered]
    if absent:
        fail("PHD_ERRORS names %s, which no rendered vocabulary header defines" % absent)
    # the daemon is compiled against the rendered numbers: one that is not the declared resp of its code is a stale render
    for pkg, docs in (("plugin-hostd-protocol", own_docs), ("host", shared_docs)):
        for ref, (code, resp) in codes_of(docs).items():
            macro = "OMX_" + re.sub(r"[^A-Za-z0-9]+", "_", code).upper() + "_RESP"
            if resp is not None and macro in rendered and rendered[macro] != resp:
                fail("%s is %d in the rendered header and %d in %s (%s): render again" % (macro, rendered[macro], resp, pkg, ref))
    errors = {rendered[n] for n in names}
    if len(errors) < 20:
        fail("found only %d numbers in protocol.h's PHD_ERRORS" % len(errors))
    unnamed = sorted(errors - set(named))
    if unnamed:
        fail("protocol.h answers %s, which no code of the domains plugin-hostd-protocol and host names" % unnamed)
    print("ok   one name per number: %d numbers, %d of protocol.h's, %d of them named by the domain host"
          % (len(named), len(errors), len([r for r in errors if any(n.startswith("host ") for n in named.get(r, []))])))


def contract_dirs():
    dirs = [d for d in os.environ.get("OMX_CONTRACT_PATH", "").split(":") if d]
    p = subprocess.run([os.environ.get("PKG_CONFIG", "pkg-config"), "--variable=contractdir", "omx-contract"],
                       capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        dirs.append(p.stdout.strip())
    return dirs


def domain_docs(owner):
    """the data form of every domain <owner> owns in the contract directory (plugin-hostd-protocol's domain host holds
    HOST_REPLY_CODES, HOST_TRACK_KINDS and HOST_EVENTS, omx-clap's domain hosting its window codes), as tables the
    readers here read"""
    out, seen = [], set()
    for d in contract_dirs():
        for e in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            path = os.path.join(d, e, e + ".json")
            if e in seen or not os.path.isfile(path):
                continue
            with open(path) as f:
                doc = json.load(f)
            if not isinstance(doc, dict) or doc.get("info", {}).get("x-owner") != owner:
                continue
            seen.add(e)
            try:
                out.extend(json.loads(text) for text in protocol_files.rebuild(e, path).values())
            except RuntimeError as err:
                fail(str(err))
    return out


PROTOCOL, CLAP = "plugin-hostd-protocol", "omx-clap"
SHARED_VERBS = ("PLUGIN_HOSTD_PROTOCOL_SHARED_VERBS", "PLUGIN_HOSTD_PROTOCOL_CLAP_HOST_VERBS")
# the one home of each item omx-clap's package held once (ruling R5): the verbs both hosts answer, the reply codes, the
# track kinds and the events are the protocol's (its domains plugin-hostd-protocol and host), the window codes omx-clap's
# (its domain hosting, omx-clap-core#156); each is read from its owner's domains only
HOMES = dict([(k, PROTOCOL) for k in SHARED_VERBS + ("HOST_REPLY_CODES", "HOST_TRACK_KINDS", "HOST_EVENTS")],
             HOSTING_WINDOW_CODES=CLAP)


def items_of(docs):
    return {k for doc in docs for k, v in doc.items() if isinstance(v, dict) and "kind" in v}


def moved_refusals(package_docs, domains):
    """why the items of HOMES are not read from their owners' domains alone: each one omx-clap's package tables hold
    (whether or not a domain holds it too), and each one no domain of its owner holds; [] when every one is its owner's
    domain's and none the package's. domains is {owner: its domains' tables}"""
    in_package = items_of(package_docs)
    out = ["%s is in omx-clap's package: it is read from %s's domains only" % (k, HOMES[k]) for k in HOMES if k in in_package]
    out += ["%s is in no domain of %s: it is read from %s's domains only" % (k, HOMES[k], HOMES[k])
            for k in HOMES if k not in items_of(domains.get(HOMES[k], []))]
    return out


def moved_arms(docs, domains):
    """sabotage, three arms: HOST_EVENTS planted in a copy of omx-clap's package tables is refused while the protocol's
    domain holds it, and refused (with the domain's absence named) when the domain's copy is removed too; and every
    item of HOMES in the package with every domain emptied"""
    events = next((doc["HOST_EVENTS"] for doc in domains[PROTOCOL] if "HOST_EVENTS" in doc), None)
    if events is None:
        fail("sabotage: no domain of plugin-hostd-protocol holds HOST_EVENTS to plant")
        return
    planted = [dict(docs[0], HOST_EVENTS=events) if docs else {"HOST_EVENTS": events}] + docs[1:]
    got = moved_refusals(planted, domains)
    if any(r.startswith("HOST_EVENTS is in omx-clap's package") for r in got):
        print("ok   sabotage: HOST_EVENTS planted in omx-clap's package is refused by name, the domain holding it too")
    else:
        fail("sabotage: HOST_EVENTS planted in omx-clap's package is not refused: %s" % got)
    without = dict(domains, **{PROTOCOL: [{k: v for k, v in doc.items() if k != "HOST_EVENTS"} for doc in domains[PROTOCOL]]})
    got = moved_refusals(planted, without)
    if any(r.startswith("HOST_EVENTS is in omx-clap's package") for r in got) and \
            any(r.startswith("HOST_EVENTS is in no domain") for r in got):
        print("ok   sabotage: HOST_EVENTS in the package alone, the domain's copy removed, is refused and its absence named")
    else:
        fail("sabotage: HOST_EVENTS in the package alone is read from the old home: %s" % got)
    # every item of HOMES in a copy of the package's tables, every domain emptied: each is refused in the package and
    # named missing from its owner's domains
    held = {k: v for owner in domains for doc in domains[owner] for k, v in doc.items() if k in HOMES}
    full = [dict(docs[0], **held) if docs else dict(held)] + docs[1:]
    got = moved_refusals(full, {})
    missing = [k for k in HOMES if not (any(r.startswith(k + " is in omx-clap's package") for r in got) and
                                        any(r.startswith(k + " is in no domain") for r in got))]
    if len(held) == len(HOMES) and not missing:
        print("ok   sabotage: the domains emptied and the package holding the shared verbs, HOST_REPLY_CODES, "
              "HOST_TRACK_KINDS, HOST_EVENTS and HOSTING_WINDOW_CODES: each refused in the package and named missing "
              "from its owner's domains")
    else:
        fail("sabotage: with the domains emptied the package's copy is read for %s (planted %s)" % (missing, sorted(held)))


def package_tables(name):
    """the tables of a package of the contract directory alone (its MANIFEST's files), [] when none holds it"""
    for d in contract_dirs():
        base = os.path.join(d, name)
        manifest = os.path.join(base, "MANIFEST.json")
        if os.path.exists(manifest):
            with open(manifest) as f:
                m = json.load(f)
            docs = []
            for rel in m["files"]:
                with open(os.path.join(base, rel)) as f:
                    docs.append(json.load(f))
            return docs
    return []


def package(name):
    """the files of a package of the contract directory and of the domains its owner owns, and where they were read,
    or (None, None)"""
    for d in contract_dirs():
        base = os.path.join(d, name)
        manifest = os.path.join(base, "MANIFEST.json")
        if os.path.exists(manifest):
            with open(manifest) as f:
                m = json.load(f)
            docs = []
            for rel in m["files"]:
                with open(os.path.join(base, rel)) as f:
                    docs.append(json.load(f))
            domains = domain_docs(name)
            if name == CLAP:
                for why in moved_refusals(docs, {CLAP: domains, PROTOCOL: domain_docs(PROTOCOL)}):
                    fail("%s (%s)" % (why, base))
                # the items of HOMES are read from their owners' domains alone, never from the package's tables
                docs = [{k: v for k, v in doc.items() if k not in HOMES} for doc in docs]
            return docs + domains, "%s %s from %s" % (name, m["version"], base)
    return None, None


def owes(verb, host):
    return verb["implementedBy"].get(host) in ("required", "optional")


# ---------------------------------------------------------------- a reply and its declared shape

WORD = re.compile(r'"(?:[^"\\]|\\.)*"|\S+')


def words(line):
    return WORD.findall(line)


def token_rx(token):
    if "..." in token:
        return r"\S+"
    if token.startswith('"') and token.endswith('"'):
        return r'"(?:[^"\\]|\\.)*"'
    parts = re.split(r"(<[^>]+>)", token)
    return "".join(r'(?:"(?:[^"\\]|\\.)*"|[^\s"]+?)' if p.startswith("<") else re.escape(p) for p in parts if p)


def shaped(reply, declared):
    """whether reply is declared's shape: its literal words, one word per placeholder, and a last ... the placeholder
    before it again none or more times; a count in second place (resp <n> or resp <count>) is a whole number and the
    words after it are that many records"""
    got, want = words(reply), declared.split()
    if len(got) < 2 or got[0] != want[0]:
        return False
    # a last ... repeats the placeholder before it none or more times (hello's extensions)
    if want[-1] == "...":
        want = want[:-2] + want[-2:-1] * max(0, len(got) - (len(want) - 2))
    if want[1].startswith("<"):
        if not re.fullmatch(r"[0-9]+", got[1]):
            return False
        rest = want[2:]
        want = want[:2] + rest * int(got[1]) if rest else want
    if len(got) != len(want):
        return False
    return all(re.fullmatch(token_rx(w), g) for g, w in zip(got[1:], want[1:]))


def takes(fmt, line):
    """whether the declared format takes the line: the verb, then a word per conversion, %i a whole number, and more
    words only where it ends in ..."""
    want, got = fmt.split(), words(line)
    if got[0] != want[0]:
        return False
    open_end = want[-1] == "..."
    conv = [w for w in want[1:] if w != "..."]
    if len(got) - 1 < len(conv) or (not open_end and len(got) - 1 != len(conv)):
        return False
    return all(c != "%i" or re.fullmatch(r"-?[0-9]+", g) for c, g in zip(conv, got[1:]))


# the code words the declarations hold, of either package (main fills it): a refusal may carry one after its number
CODE_WORDS = set()


def code(reply):
    """the refusal number of a reply; param_set_many's carries the position of the pair it refused after it, and a
    refusal may carry a declared code word after it (resp -902 hosting.window.no-display)"""
    m = re.fullmatch(r"resp (-[0-9]+)(?: [1-9][0-9]*| (\S+))?", reply)
    if not m or (m.group(2) is not None and m.group(2) not in CODE_WORDS):
        return None
    return int(m.group(1))


# ---------------------------------------------------------------- the lines

# For each verb plugin-hostd owes, in the order they run: the arguments of a well-formed line, of a malformed one, and
# of lines the verb refuses by its meaning, each of which must answer a code the verb declares. {uri} is the CLAP
# fixture's uri (an add made 1 and 2 of it, and its scan wrote its descriptor and its panel; their first-use pins are
# recorded), 3 is an LV2 instance on mod-host's row, {layout} the fake's layout pin, {sha} the CLAP file's SHA-256.
# pin_accept takes the first-use pin before pin_set replaces it with one of verdict in-process, which lets the members
# share the chain's worker; chain_get and chain_clear read and forget what chain declared; pin_clear runs last.
LINES = {
    "hello": ("1 tags", "x", ("0 tags",)),
    "param_get_many": ("1 :bypass", "", ("99 gain",)),
    "param_set_many": ("1 gain 0.5", "", ("99 gain 0.5", "1 gain loud")),
    "pin_accept": ("{uri}", "", ()),
    "pin_set": ("{uri} controls.clap={sha} {layout} verdict=in-process", "{uri}", ()),
    "worker_list": ("", "x", ()),
    "instance_info": ("1", "1 x", ("99",)),
    "supervisor_reset": ("all", "all x", ("w99",)),
    "quarantine_clear": ("all", "", ("99",)),
    "policy_set": ("clap own", "clap", ("clap pool:",)),
    "pool_config": ("p 4", "p x", ()),
    "worker_env": ("clap - -", "clap", ()),
    "lv2_worker_set": ("urn:example:other mod-host", "urn:example:other", ()),
    "descriptor_get": ("{uri}", "{uri} x", ("clap:/nowhere.clap#x",)),
    "panel_get": ("{uri}", "", ("clap:/nowhere.clap#x",)),
    "description_get": ("{lv2}", "", ("clap:/nowhere.clap#x",)),
    "preset_list": ("1", "", ("99", "3")),
    "preset_get": ("1 0", "1", ("99 0", "3 0")),
    "track_info": ('1 "Lead" #112233', "1", ("99 x -",)),
    "node_label": ("1 Lead", "", ("99 x",)),
    "remote_pages": ("1", "", ("99",)),
    "remote_page_get": ("1 0", "1", ("99 0",)),
    "param_info": ("1 0", "1", ("99 x",)),
    "note_input": ("1", "", ("99",)),
    "note_on": ("1 0 60 100", "1 0 60", ("99 0 60 100",)),
    "note_off": ("1 0 60 0", "1 0 60", ("99 0 60 0",)),
    "all_notes_off": ("1", "", ("99",)),
    "hide_external_ui": ("1", "1 x", ("99",)),
    "property_list": ("1", "1 x", ("99",)),
    "property_info": ("1 0", "1", ("99 0", "1 5")),
    "property_get": ("1 file", "1", ("99 file", "1 nope", "1 writeonly_key")),
    "property_set": ('1 file "/tmp/take.wav"', "1 file", ("99 file x", "1 readonly_mode x")),
    "curve_bind": ("1 0 transfer_curve dynamics threshold=0:dB ratio=1:ratio", "1 x transfer_curve", ("99 0 transfer_curve dynamics threshold=0:dB",)),
    "curve_points": ("1 0 9", "1 x 9", ("99 0 9",)),
    "monitor_output_off": ("1 out", "1", ()),
    "chain": ("7 1 2", "7", ("8 99", "8 1 1")),
    "chain_get": ("7", "x", ("9",)),
    "chain_clear": ("7", "x", ("7",)),
    "history_get": ("{uri}", "", ()),
    "history_clear": ("clap:/nowhere.clap#x", "", ()),
    "plan": ("7 1 2", "7", ("8 99", "8 1 1")),
    "plan_get": ("7", "x", ("9",)),
    "plan_clear": ("7", "x", ("7",)),
    "estimate": ("48000 128 {uri} {uri}", "48000", ("0 128 {uri}", "48000 x {uri}")),
    "pin_reload": ("", "x", ()),
    "pin_changed": ("", "a b c d", ()),
    "pin_clear": ("all", "", ()),
}
ORDER = list(LINES)


def line(verb, args, ctx):
    return (verb + " " + args.format(**ctx)).strip()


def setup(s):
    """a daemon in front of the fake worker under pin_mode first-use, with two CLAP instances whose scan is done and
    an LV2 one; the first-use pins of the CLAP adds are recorded, so pin_accept takes them; {lv2} is the LV2 plugin's
    uri, which a layer of the run's descriptions store holds"""
    lay = subprocess.check_output([FAKE, "-L"], text=True).strip()
    # a descriptions store of the run's own, a layer of it holding the LV2 plugin: description_get answers its key
    store = Store()
    close = s.close
    s.close = lambda: (store.close(), close())
    lv2 = "lv2:%s" % scan_fixture.LV2_COMPRESSOR
    store.put(scan_fixture.sha(os.path.join(s.bundle, "pinned.so")), "lv2", scan_fixture.LV2_COMPRESSOR, store.source("lv2", s.bundle))
    d = s.daemon(conf={"require_pins": 1, "pin_mode": "first-use", "clap_path": s.dir}, env=store.daemon_env())
    for n in (1, 2):
        d.expect("add %s %d" % (s.clap_uri, n), "resp %d" % n)
    d.expect("add lv2:%s 3" % scan_fixture.LV2_COMPRESSOR, "resp 3")
    # R-112: a plugin with no verdict is bypassed until its check or the operator's choice: these are the operator's
    d.expect("pin_accept %s" % s.clap_uri, "resp 0")
    d.expect("pin_accept lv2:%s" % scan_fixture.LV2_COMPRESSOR, "resp 0")
    wait_for(lambda: d.send("panel_get %s" % s.clap_uri).startswith("resp 0 "), "the scan's descriptor and panel")
    return d, {"uri": s.clap_uri, "lv2": lv2, "layout": lay, "sha": scan_fixture.sha(s.clap)}


def check_verbs(declared, shared):
    s = scan_fixture.Scan(lambda **kw: Daemon(EXE, FAKE, **kw))
    d = None
    try:
        d, ctx = setup(s)
        owed = [v for v in declared if owes(declared[v], HOSTD)]
        # every verb the installed declaration gives plugin-hostd is owed: the tree builds on the protocol installed, and
        # there is no floor release whose later verbs it could set aside
        missing = [v for v in owed if v not in LINES]
        if missing:
            fail("no well-formed line for %s, which the declarations give plugin-hostd" % missing)
        for verb in sorted((v for v in owed if v in LINES), key=ORDER.index):
            decl = declared[verb]
            good, bad = (line(verb, a, ctx) for a in LINES[verb][:2])
            if not takes(decl["format"], good):
                fail("%s: the well-formed line %r is not what its declared format %r takes" % (verb, good, decl["format"]))
                continue
            r = d.send(good)
            optional = decl["implementedBy"][HOSTD] == "optional"
            if shaped(r, decl["reply"]):
                print("ok   %-16s %-40s -> %s" % (verb, good[:40], r[:60]))
            elif optional and code(r) in decl["codes"]:
                print("ok   %-16s %-40s -> %s (optional: a declared refusal)" % (verb, good[:40], r))
            else:
                fail("%s: %r answers %r, not the declared %r%s" % (verb, good, r, decl["reply"],
                     " or one of %s" % decl["codes"] if optional else ""))
            # a format that ends in ... takes any words past its conversions: the grammar past them is the verb's own
            if not decl["format"].endswith("...") and takes(decl["format"], bad):
                fail("%s: the malformed line %r is one its declared format %r takes" % (verb, bad, decl["format"]))
            for kind, refused in [("malformed", bad)] + [("refused", line(verb, a, ctx)) for a in LINES[verb][2]]:
                r = d.send(refused)
                if code(r) is not None and code(r) in decl["codes"]:
                    print("ok   %-16s %-40s -> %s (declared)" % (verb, refused[:40], r))
                else:
                    fail("%s: the %s %r answers %r, which is none of its declared codes %s"
                         % (verb, kind, refused, r, decl["codes"]))
    except Fail as e:
        fail(str(e))
    finally:
        if d:
            d.close()
        s.close()


# ---------------------------------------------------------------- what the daemon answers itself

def binary_words(exe):
    """every lower-case word the binary holds as a C string: each word the daemon compares a verb with is one"""
    with open(exe, "rb") as f:
        data = f.read()
    return sorted({w.decode() for w in re.findall(rb"(?<=\x00)([a-z][a-z0-9_]{2,40})(?=\x00)", data)})


def answered_by_daemon(candidates):
    """the words whose line the daemon answers without relaying it: a line of eleven words no verb takes, sent with one
    worker up, that never reaches the worker"""
    log = harness.scratch_path("plugin-hostd-verbs-log.")
    s = scan_fixture.Scan(lambda **kw: Daemon(EXE, FAKE, **kw))
    d = s.daemon(env={"FAKE_LOG": log})
    try:
        d.expect("add %s 1" % s.clap_uri, "resp 1")
        junk = " ~" * 11
        for w in candidates:
            d.send(w + junk)
        d.send("worker_list")
        with open(log) as f:
            relayed = {l.split(" ", 2)[1] for l in f if l.endswith(junk + "\n")}
        return {w for w in candidates if w not in relayed}
    finally:
        d.close()
        s.close()
        if os.path.exists(log):
            os.unlink(log)


def check_answered(declared):
    with open(protocol_files.variable("modhostjson")) as f:
        modhost = {c["verb"] for c in json.load(f)["commands"]}
    candidates = binary_words(EXE)
    ours = {v for v in declared if owes(declared[v], HOSTD)}
    unseen = ours - set(candidates)
    if unseen:
        fail("positive control: the scan of the binary does not see the declared %s" % sorted(unseen))
    answered = answered_by_daemon(candidates)
    extra = answered - ours - modhost
    if extra:
        fail("the daemon answers %s itself, which no declaration and no mod-host command holds" % sorted(extra))
    relayed = ours - answered
    if relayed:
        fail("declared for plugin-hostd, but the daemon relays them and never answers them: %s" % sorted(relayed))
    if not extra and not relayed:
        print("ok   the daemon answers %d words of its %d itself: the %d declared for it and %d of mod-host's"
              % (len(answered), len(candidates), len(ours), len(answered - ours)))


# ---------------------------------------------------------------- the same line to both hosts

class Worker:
    """tests/fake-host on ports of its own, as a daemon starts it; it answers once a controller holds both"""

    def __init__(self):
        self.port, fb = harness.port_pair()
        self.proc = subprocess.Popen([FAKE, "-p", str(self.port), "-f", str(fb)], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        end = time.monotonic() + 10
        while True:
            try:
                self.sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
                self.client = plugin_hostd_client.Client(self.sock)
                self.fb = socket.create_connection(("127.0.0.1", fb), timeout=10)
                break
            except OSError:
                if time.monotonic() > end:
                    raise Fail("the fake worker does not listen on %d and %d" % (self.port, fb))
                time.sleep(0.02)

    def send(self, msg):
        try:
            return self.client.send(msg)
        except ConnectionError:
            raise Fail("the fake worker closed on " + msg)

    def close(self):
        self.proc.kill()
        self.proc.wait()


def check_both(declared):
    both = [v for v in declared if owes(declared[v], HOSTD) and owes(declared[v], CLAP_HOST) and v in LINES]
    s = scan_fixture.Scan(lambda **kw: Daemon(EXE, FAKE, **kw))
    d = w = None
    try:
        d, ctx = setup(s)
        # the members share a worker under a pin of verdict in-process, as in check_verbs
        d.expect(line("pin_set", LINES["pin_set"][0], ctx), "resp 0")
        w = Worker()
        for n in (1, 2):
            w.send("add %s %d" % (s.clap_uri, n))
        for verb in sorted(both, key=ORDER.index):
            decl = declared[verb]
            good = line(verb, LINES[verb][0], ctx)
            a, b = d.send(good), w.send(good)
            same = (shaped(a, decl["reply"]) and shaped(b, decl["reply"])) or (code(a) is not None and code(a) == code(b))
            # a verb optional of a host may be refused by it with a code it declares, while the other answers it: the
            # session verbs (hello), which each host answers for its own connection, are such
            def refused(r, host):
                return decl["implementedBy"].get(host) == "optional" and code(r) is not None and code(r) in decl["codes"]
            if same:
                print("ok   %-16s the same shape from both hosts: %s | %s" % (verb, a[:40], b[:40]))
            elif (shaped(a, decl["reply"]) or refused(a, HOSTD)) and (shaped(b, decl["reply"]) or refused(b, CLAP_HOST)):
                print("ok   %-16s each host's declared answer: %s | %s (optional: a declared refusal)" % (verb, a[:40], b[:40]))
            else:
                fail("%s: %r answers %r from plugin-hostd and %r from the worker, not one declared shape" % (verb, good, a, b))
    except Fail as e:
        fail(str(e))
    finally:
        if w:
            w.close()
        if d:
            d.close()
        s.close()


def main():
    protocol = protocol_files.verbs()
    # the domain's own tables: the daemon's verbs and codes, and the verbs both hosts answer
    own_docs = [{k: v for k, v in protocol.items() if k not in SHARED_VERBS}]
    shared_docs = [{k: v for k, v in protocol.items() if k in SHARED_VERBS}]
    clap, source = package(CLAP)
    if not clap:
        fail("no omx-clap-core package in OMX_CONTRACT_PATH or the contract directory: the window verbs refuse with its "
             "HOSTING_WINDOW_CODES")
        return 1
    # the protocol's other domains (host: the codes, track kinds and events of both hosts), without the one read above
    hosts = [doc for doc in domain_docs(PROTOCOL) if not set(doc) & set(protocol) - {"requires"}]
    docs = hosts + clap
    moved_arms(package_tables(CLAP), {CLAP: domain_docs(CLAP), PROTOCOL: domain_docs(PROTOCOL)})
    own = verbs_of(own_docs, own_docs + docs)
    shared = verbs_of(shared_docs, own_docs + docs)
    if not shared:
        fail("the domain plugin-hostd-protocol holds no verb of %s" % " or ".join(SHARED_VERBS))
    CODE_WORDS.update(c for c, _ in codes_of(own_docs + docs).values())
    print("ok   the codes of both hosts are read from the protocol's domain host, the window codes from %s" % source)
    dup = set(shared) & set(own)
    if dup:
        fail("declared as the daemon's own and as a verb of both hosts: %s" % sorted(dup))
    print("ok   the protocol's verbs are read from %s" % OWN)
    declared_verbs = dict(shared, **own)
    check_one_name(own_docs, docs)
    # the words and the formats protocol.h names for both hosts are the declared ones
    header = protocol_files.read_header("protocol.h", TREE)
    word = dict(re.findall(r'^#define\s+(PHD_VERB_\w+)\s+"(\w+)"', header, re.M))
    named = 0
    for macro, verb_macro, rest in re.findall(r'^#define\s+(PHD_VERB_\w+)_FMT\s+(PHD_VERB_\w+) "([^"]*)"', header, re.M):
        verb = word[verb_macro]
        if verb in shared:
            named += 1
            if verb + rest != shared[verb]["format"]:
                fail("protocol.h's %s_FMT is %r, the domain declares %r" % (macro, verb + rest, shared[verb]["format"]))
    print("ok   protocol.h names %d formats of the shared verbs, as the domain declares them" % named)
    # the word after a window verb's -902 from a daemon with no display is omx-clap-core's code for that fact
    window = {c for c, _ in codes_of([{k: v for d in docs for k, v in d.items() if k == "HOSTING_WINDOW_CODES"}]).values()}
    no_display = re.search(r'^#define\s+PHD_EXTERNAL_UI_NO_DISPLAY\s+"([^"]+)"', header, re.M)
    if not no_display or no_display.group(1) not in window:
        fail("protocol.h's PHD_EXTERNAL_UI_NO_DISPLAY is %r, none of omx-clap-core's HOSTING_WINDOW_CODES %s"
             % (no_display and no_display.group(1), sorted(window)))
    else:
        print("ok   protocol.h's no-display word %s is omx-clap-core's HOSTING_WINDOW_CODES code" % no_display.group(1))
    # the line a worker writes on its feedback port that the daemon reads is the HOST_EVENTS word of the protocol's domain host
    events = {}
    for doc in docs:
        item = doc.get("HOST_EVENTS")
        if isinstance(item, dict) and item.get("kind") == "words":
            events = {k: w["word"] for k, w in item["words"].items()}
    xruns = re.search(r'^#define\s+PHD_EVENT_XRUNS\s+"(\w+)"', header, re.M)
    if "xruns" not in events:
        fail("the domain host declares no HOST_EVENTS.xruns: the daemon reads that line (%s)" % protocol.get("requires"))
    elif not xruns or xruns.group(1) != events["xruns"]:
        fail("protocol.h's PHD_EVENT_XRUNS is %r, the domain host's HOST_EVENTS.xruns is %r" % (xruns and xruns.group(1), events["xruns"]))
    else:
        print("ok   protocol.h reads the worker's %s line, as the domain host's HOST_EVENTS declares it" % events["xruns"])
    print("the protocol declares %d verbs of the daemon's own and %d of both hosts, %d of them owed by plugin-hostd" %
          (len(own), len(shared), len([v for v in declared_verbs if owes(declared_verbs[v], HOSTD)])))

    check_verbs(declared_verbs, set(shared))
    check_answered(dict(shared, **declared_verbs))
    check_both(declared_verbs)

    # positive controls of the shape and the format: a reply or a line that is not the declared one is seen
    for reply, decl, want in (("resp 0", "resp 0", True), ("resp 1", "resp 0", False),
                              ('resp 0 "/x"', 'resp 0 "<path>"', True), ("resp 0 /x", 'resp 0 "<path>"', False),
                              ("resp 2 a:1 b:2", "resp <n> <w>:<p>", True), ("resp 2 a:1", "resp <n> <w>:<p>", False),
                              ("resp 0 w4 1 1,2", "resp 0 <worker> <instance>,... <instance>,...", True)):
        if shaped(reply, decl) != want:
            fail("positive control: %r against %r is %s" % (reply, decl, not want))
    for fmt, l, want in (("chain %i %i ...", "chain 7 1 2", True), ("chain %i %i ...", "chain x 1", False),
                         ("chain_get %i", "chain_get 7 8", False), ("worker_list", "worker_list", True)):
        if takes(fmt, l) != want:
            fail("positive control: %r against %r is %s" % (l, fmt, not want))

    print("verbs declared: %s" % ("FAILED (%d)" % len(failures) if failures else "ok"))
    return 1 if failures else 0


sys.exit(main())
