# SPDX-License-Identifier: GPL-3.0-or-later
# The format tables cover their format, every field once (docs/formats.md#the-coverage-test). The field list of a format
# is every term of that format's domain (LV2: plugin-db's lv2, CLAP: omx-clap's clap) plus every row of the table with a `from`; each
# field has exactly one row. Per field it prints `mapped <word> <transform>`, `extension <format>` or
# `dropped <decision>`, then the count per class, and it is red, naming the field, for: a field with no row or with two; a
# row that covers no field; a row keyed other than its field; a word the descriptor schema lacks, or a lookup entry that
# is no value the word takes; a transform that is not in TRANSFORMS(X), a lookup with no values or not one to one, a
# scale-by with no factor, data a transform takes none of; a used TERM that is dropped, a drop with no decision; an
# outbound-read row whose transform is none a generator reads backwards; a unit row that does not map to its TERM's word;
# a unit-id or designation-meaning row with values, with no pair in its owner's mapping, or a unit id that is no
# PARAM_UNITS id with a dimension; a row an owner's mapping covers written as a lookup of its own (M5, #215).
#
#   format_coverage.py [--contract-dir <dir>] [--major <n>] [--schema <file>] <format>...
#   format_coverage.py --self-test [the same options]   each sabotage arm (a row removed, a word misspelt, a transform
#                                                       renamed) red naming its field, then the tables as they are green
#
# The TERMs are the items of the domain <contract-dir>/<lv2|clap>/<lv2|clap>.json; contract-dir is pkg-config's
# contractdir of omx-contract, the schema omx-contract.schema.json in its datadir; the tables are this tree's domains plugin-hostd/clap and plugin-hostd/lv2 (contract.d/plugin-hostd/).
import argparse, copy, json, os, re, subprocess, sys, tempfile

import jsonschema

import format_tables

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_CONFIG = os.environ.get("PKG_CONFIG", "pkg-config")
MAPS = format_tables.ITEMS
OUTBOUND = ("identity", "lookup", "unit-id", "designation-meaning")
OWNED = ("unit-id", "designation-meaning")


def pkg_var(name):
    r = subprocess.run([PKG_CONFIG, "--variable=" + name, "omx-contract"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def transforms(path):
    """The names of TRANSFORMS(X), read from the header."""
    text = open(path).read()
    body = re.search(r"#define TRANSFORMS\(X\)(.*?)\n\n", text, re.S)
    if not body:
        sys.exit("format_coverage: no TRANSFORMS(X) in %s" % path)
    return set(re.findall(r'X\("([a-z0-9-]+)"', body.group(1)))


# the domain each format's TERMs are items of, and its owner: LV2's are plugin-db's domain lv2, CLAP's omx-clap's domain clap
# (the sorting pass, V27a/V27b); omx-contract holds no format term
TERM_DOMAINS = {"lv2": ("lv2", "plugin-db"), "clap": ("clap", "omx-clap")}


def terms(contract_dir, major, fmt):
    """Every term of a format, from the items of its domain (x-kind terms, x-format <fmt>): <ITEM>#<term> -> (term name,
    term). The domain is <contract-dir>/<domain>/<domain>.json, as a reader reads a domain; major is unused, kept for the
    caller's signature."""
    domain, owner = TERM_DOMAINS[fmt]
    path = os.path.join(contract_dir, domain, domain + ".json")
    if not os.path.isfile(path):
        sys.exit("format_coverage: no domain %s under %s (%s's contract package installed?)" % (domain, contract_dir, owner))
    out = {}
    for name, item in json.load(open(path))["components"]["schemas"].items():
        if item.get("x-kind") == "terms" and item.get("x-format") == fmt:
            for w in item["oneOf"]:
                out["%s#%s" % (name, w["title"])] = (w["title"], w["x-term"])
    if not out:
        sys.exit("format_coverage: the domain %s holds no %s term (%s)" % (domain, fmt, path))
    return out


def domain_doc(contract_dir, domain, owner):
    path = os.path.join(contract_dir, domain, domain + ".json")
    if not os.path.isfile(path):
        sys.exit("format_coverage: no domain %s under %s (%s's contract package installed?)" % (domain, contract_dir, owner))
    return json.load(open(path))["components"]["schemas"]


def owners(contract_dir):
    """The owners' mappings the M5 rows read (docs/formats.md, Lookup values the owners publish), and PARAM_UNITS:
    { clap: {code: id}, lv2_units: [(terms item, term, id)], lv2_urns: {uri: id}, meanings: [(terms item, term, meaning)],
    units: {id: dimension} }"""
    lv2 = domain_doc(contract_dir, "lv2", "plugin-db")
    clap = domain_doc(contract_dir, "omx-param-contract", "omx-clap")
    param = domain_doc(contract_dir, "param", "omx-contract")

    def by_term(item):
        return [(f["$ref"].rsplit("/", 1)[-1], f["x-term"], w["const"]) for w in lv2.get(item, {}).get("oneOf", [])
                for f in w.get("x-from", [])]
    return {"clap": clap.get("OMX_PARAM_CONTRACT_UNIT_IDS", {}).get("x-value", {}),
            "lv2_units": by_term("LV2_UNIT_IDS"), "meanings": by_term("LV2_DESIGNATION_MEANINGS"),
            "lv2_urns": {w["x-uri"]: w["const"] for w in lv2.get("LV2_OPENMIXER_UNIT_IDS", {}).get("oneOf", []) if "x-uri" in w},
            "units": {w["const"]: w.get("x-dimension") for w in param.get("PARAM_UNITS", {}).get("oneOf", [])}}


def owner_pairs(fmt, key, row, tr, own):
    """The pairs an owner's mapping gives a unit-id or designation-meaning row, as describe reads them."""
    if fmt == "clap":
        return dict(own["clap"]) if tr == "unit-id" else {}
    term = row.get("term") or ""
    if tr == "unit-id" and term == "LV2_UNITS_TERMS#unit":
        return dict(own["lv2_urns"])
    item, _, name = term.partition("#")
    return {key: v for i, t, v in own["lv2_units" if tr == "unit-id" else "meanings"] if i == item and t == name}


class Schema:
    """The descriptor's words, walked in omx-contract's schema."""

    def __init__(self, path):
        self.doc = json.load(open(path))
        self.defs = self.doc["$defs"]
        self.cls = jsonschema.validators.validator_for(self.doc)

    def resolve(self, node):
        while isinstance(node, dict) and "$ref" in node:
            node = self.defs[node["$ref"].rsplit("/", 1)[1]]
        return node

    def word(self, path):
        """The schema of a word (`controls[].travel.unit`), or None when the descriptor has no such word."""
        node = self.resolve(self.defs["descriptor"])
        for seg in path.split("."):
            many = seg.endswith("[]")
            node = self.resolve((node.get("properties") or {}).get(seg[:-2] if many else seg))
            if not isinstance(node, dict):
                return None
            if many:
                if node.get("type") != "array":
                    return None
                node = self.resolve(node.get("items"))
        return node

    def takes(self, node, value):
        """Whether a word takes the value: an item of it when the word is a list."""
        if node.get("type") == "array" and not isinstance(value, list):
            node = self.resolve(node.get("items", {}))
        return self.cls({"$defs": self.defs, **node}).is_valid(value)


def check(fmt, table, installed, schema, names, own):
    """(lines, reds, counts): every field of the format with its row's class, and what is red."""
    item = table.get("components", {}).get("schemas", {}).get(MAPS[fmt])
    if not isinstance(item, dict) or item.get("x-kind") != "map" or item.get("x-format") != fmt \
            or not isinstance(item.get("oneOf"), list):
        return [], ["%s: no x-kind map %s of format %s" % (fmt, MAPS[fmt], fmt)], {}
    rows = format_tables.rows(table, fmt)
    lines, reds, counts = [], [], {"mapped": 0, "extension": 0, "dropped": 0}
    red = lambda field, why: reds.append("RED %s %s: %s" % (fmt, field, why))
    covers = {}
    for key, row in rows.items():
        field = row.get("term") if "term" in row else key
        covers.setdefault(field, []).append(key)
        if "term" in row and row["term"] not in installed:
            red(key, "covers no field: %s is no installed term" % row["term"])
    fields = list(installed) + [k for k, r in rows.items() if "from" in r]
    for field in fields:
        keys = covers.get(field, [])
        if not keys:
            red(field, "no row")
            continue
        if len(keys) > 1:
            red(field, "%d rows: %s" % (len(keys), ", ".join(sorted(keys))))
        key = keys[0]
        row = rows[key]
        term = installed.get(row.get("term"))
        if term:
            name, t = term
            want = t["id"] if fmt == "clap" else None
            if (want is not None and key != want) or (want is None and key.split(":", 1)[-1] != name):
                red(key, "keyed other than its field %s" % row["term"])
        classes = [c for c in ("word", "extension", "dropped") if c in row]
        if len(classes) != 1:
            red(key, "%d classes" % len(classes))
            continue
        if "word" in row:
            w = row["word"]
            word, tr = w.get("word", ""), w.get("transform", "")
            lines.append("%s: mapped %s %s" % (key, word, tr))
            counts["mapped"] += 1
            node = schema.word(word)
            if node is None:
                red(key, "word %s: the descriptor schema has no such word" % word)
            if tr not in names:
                red(key, "transform %s: not in TRANSFORMS(X)" % tr)
            if tr == "lookup":
                values = w.get("values")
                if not values:
                    red(key, "lookup with no values")
                else:
                    seen = [json.dumps(v) for v in values.values()]
                    if len(set(seen)) != len(seen):
                        red(key, "lookup not one to one: %s" % json.dumps(values))
                    for v in values.values():
                        if node is not None and not schema.takes(node, v):
                            red(key, "lookup entry %s: no value %s takes" % (json.dumps(v), word))
            elif "values" in w:
                red(key, "values on %s, which takes none" % tr)
            if tr in OWNED:
                pairs = owner_pairs(fmt, key, row, tr, own)
                if not pairs:
                    red(key, "%s: the owner's mapping holds no pair for it (a unit with no standard id is a dropped row "
                        "naming its ruling)" % tr)
                for v in pairs.values():
                    if node is not None and not schema.takes(node, v):
                        red(key, "%s pair %s: no value %s takes" % (tr, json.dumps(v), word))
                    if tr == "unit-id" and not own["units"].get(v):
                        red(key, "unit-id pair %s: no PARAM_UNITS id with a dimension" % json.dumps(v))
            elif tr == "lookup" and (word == "controls[].travel.unit" or (fmt == "lv2" and term and word == "controls[].meaning"
                                     and any(i + "#" + t == row.get("term") for i, t, _ in own["meanings"]))):
                red(key, "a lookup writing its own %s pairs: the owner's mapping gives them (unit-id, designation-meaning)"
                    % word)
            if tr == "scale-by":
                if not w.get("factor"):
                    red(key, "scale-by with no factor")
            elif "factor" in w:
                red(key, "factor on %s, which takes none" % tr)
            if term:
                name, t = term
                if t.get("kind") != "property" and any(str(b).startswith("omx-plugins:") for b in t.get("by", [])) \
                        and tr not in OUTBOUND:
                    red(key, "outbound-read (%s writes it) with transform %s, neither identity nor lookup"
                        % ("omx-plugins", tr))
                got = owner_pairs(fmt, key, row, tr, own) if tr in OWNED else w.get("values")
                if fmt == "lv2" and t.get("kind") == "unit" and t.get("word") is not None and got != {key: t["word"]}:
                    red(key, "unit row %s: its TERM names the word %s" % (json.dumps(got), t["word"]))
        elif "extension" in row:
            lines.append("%s: extension %s" % (key, fmt))
            counts["extension"] += 1
        else:
            ruling = (row["dropped"] or {}).get("ruling", "") if isinstance(row["dropped"], dict) else ""
            lines.append("%s: dropped %s" % (key, ruling))
            counts["dropped"] += 1
            if not ruling:
                red(key, "dropped by no decision")
            if term and term[1].get("status") == "used":
                red(key, "a used TERM (%s) dropped" % row["term"])
    return lines, reds, counts


def run(fmt, table, opts, quiet=False):
    lines, reds, counts = check(fmt, table, opts.installed[fmt], opts.schema, opts.names, opts.owners)
    if not quiet:
        for line in lines:
            print("%s %s" % (fmt, line))
        print("%s: %d fields: mapped %d, extension %d, dropped %d" % (fmt, sum(counts.values()), counts.get("mapped", 0),
                                                                     counts.get("extension", 0), counts.get("dropped", 0)))
    for r in reds:
        print(r)
    return reds


def self_test(opts):
    failed = 0
    for fmt in ("clap", "lv2"):
        table = opts.tables[fmt]
        rows = format_tables.rows(table, fmt)
        mapped = [k for k, r in rows.items() if "word" in r and "term" in r]
        lookup = next(k for k in mapped if rows[k]["word"]["transform"] == "lookup")
        removed, misspelt, renamed = mapped[0], mapped[len(mapped) // 2], lookup

        def arm(what, edit, names):
            nonlocal failed
            broken = copy.deepcopy(table)
            edit(format_tables.rows(broken, fmt))
            reds = run(fmt, broken, opts, quiet=True)
            ok = reds and all(any(n in r for r in reds) for n in names)
            print("self-test %s %s: %s" % (fmt, what, "red, naming %s" % " ".join(names) if ok else "NOT RED"))
            failed += not ok

        arm("one row removed", lambda r: r.pop(removed), [rows[removed]["term"]])
        arm("one word misspelt", lambda r: r[misspelt]["word"].update(word=r[misspelt]["word"]["word"] + "x"), [misspelt])
        arm("one transform renamed", lambda r: r[renamed]["word"].update(transform="look-up"), [renamed])
        # M5: a row the owner's mapping gives its pairs, written with values of its own; and back as a lookup
        owned = next(k for k, r in rows.items() if "word" in r and r["word"]["transform"] == "unit-id")
        arm("a unit-id row with values of its own", lambda r: r[owned]["word"].update(values={"x": "dB"}), [owned])
        arm("a unit row back as a lookup of its own",
            lambda r: r[owned]["word"].update(transform="lookup", values={owned: "dB"}), [owned])
        # and the owner's mapping without the row's pairs: red naming the row, as no pair
        saved = opts.owners
        opts.owners = copy.deepcopy(saved)
        if fmt == "clap":
            opts.owners["clap"] = {}
        else:
            item, _, name = rows[owned]["term"].partition("#")
            opts.owners["lv2_units"] = [x for x in saved["lv2_units"] if (x[0], x[1]) != (item, name)]
        reds = run(fmt, table, opts, quiet=True)
        opts.owners = saved
        ok = any(owned in r and "holds no pair" in r for r in reds)
        print("self-test %s the owner's mapping without the pair of %s: %s" % (fmt, owned, "red, naming it" if ok else "NOT RED"))
        failed += not ok
        # the TERMs are read from the format's domain: a scratch copy of it without the term a mapped row names is red,
        # naming that row (the read follows the domain, not a copy of its own)
        domain, _owner = TERM_DOMAINS[fmt]
        with tempfile.TemporaryDirectory() as scratch:
            doc = json.load(open(os.path.join(opts.contract_dir, domain, domain + ".json")))
            item, term = rows[removed]["term"].split("#", 1)
            words = doc["components"]["schemas"][item]["oneOf"]
            doc["components"]["schemas"][item]["oneOf"] = [w for w in words if w["title"] != term]
            os.makedirs(os.path.join(scratch, domain))
            with open(os.path.join(scratch, domain, domain + ".json"), "w") as f:
                json.dump(doc, f)
            installed = opts.installed[fmt]
            opts.installed[fmt] = terms(scratch, opts.major, fmt)
            reds = run(fmt, table, opts, quiet=True)
            opts.installed[fmt] = installed
            ok = len(words) - 1 == len(doc["components"]["schemas"][item]["oneOf"]) and any(removed in r for r in reds)
            print("self-test %s one term removed from a scratch domain %s: %s" % (fmt, domain, "red, naming %s" % removed if ok else "NOT RED"))
            failed += not ok
        reds = run(fmt, table, opts, quiet=True)
        print("self-test %s as it is: %s" % (fmt, "green" if not reds else "RED"))
        failed += bool(reds)
    print("FORMAT-COVERAGE SELF-TEST %s" % ("OK" if not failed else "FAILED"))
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--contract-dir", default=os.environ.get("CONTRACTDIR") or pkg_var("contractdir"))
    # the schema major is omx-contract's (schema_major of its pkg-config file, 3.9.0 or later), never typed here
    ap.add_argument("--major", default=os.environ.get("CONTRACT_SCHEMA_MAJOR") or pkg_var("schema_major"))
    ap.add_argument("--schema", default=os.environ.get("OMX_CONTRACT_SCHEMA")
                    or os.path.join(pkg_var("datadir"), "omx-contract.schema.json"))
    ap.add_argument("--transforms", default=os.path.join(ROOT, "src", "transforms.h"))
    ap.add_argument("formats", nargs="*", metavar="clap|lv2")
    opts = ap.parse_args()
    if any(f not in MAPS for f in opts.formats):
        ap.error("a format is clap or lv2")
    if not opts.major:
        sys.exit("format_coverage.py: pkg-config names no schema_major of omx-contract: install omx-contract-devel 3.9.0 or later, or pass --major")
    if not opts.contract_dir:
        sys.exit("format_coverage: no contract directory: install omx-contract-devel or pass --contract-dir")
    opts.schema = Schema(opts.schema)
    opts.names = transforms(opts.transforms)
    opts.tables = {f: format_tables.load(f) for f in MAPS}
    opts.installed = {f: terms(opts.contract_dir, opts.major, f) for f in MAPS}
    opts.owners = owners(opts.contract_dir)
    if opts.self_test:
        sys.exit(1 if self_test(opts) else 0)
    failed = 0
    for fmt in opts.formats or ["clap", "lv2"]:
        reds = run(fmt, opts.tables[fmt], opts)
        print("FORMAT-COVERAGE %s %s" % (fmt, "OK" if not reds else "RED (%d)" % len(reds)))
        failed += bool(reds)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
