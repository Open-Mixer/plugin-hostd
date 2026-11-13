"""matrix.py [--json] <document-or-set-directory>...: a matrix run read as one result (#48).

A matrix run is one omx-bench/1 document per rate, frame count and periods (a Raspberry Pi's set directories
r<rate>-f<frames>-n<periods>, a desk's desk-*.json). This reads them all and lays them out by PERIOD LENGTH and RATE:
rates compare at equal period length (48000/128, 96000/256 and 192000/512 are each 2.67 ms), so a row is a period in
milliseconds and a column a rate. One table per periods value: n2, n3 ... for the alsa driver (2 when a document does
not say), dummy for the dummy driver.

A cell gives, per host, its clean cells over its ok cells and the xruns summed: a row that ran (status ok) is clean
when it counted no xrun; a row that did not run (unsupported, failed) is not counted. A cell under one millisecond is
marked sub-ms (a period that short is no verdict on the rate). A set is not reachable when it ran no cell, or when its
set directory holds no document. Under each table, per rate, the SAFE MINIMUM: the shortest period whose set is
clean (no xrun in any cell that ran) with every longer period of that rate clean too; a rate whose longest set is not
clean has none.

Markdown on stdout, or with --json the same result as JSON. Exit 2 on a file that is not an omx-bench/1 document."""

import json
import os
import re
import sys

HOSTS = ("H1", "H2", "H3", "H4")
SET_DIR = re.compile(r"r(\d+)-f(\d+)-n(\d+)$")


class NotADocument(Exception):
    pass


def period_ms(rate, frames):
    return round(frames * 1000.0 / rate, 2)


def key(ms):
    """a period's key in the report's maps: its milliseconds to two decimals"""
    return "%.2f" % ms


def periods_of(doc):
    jack = doc.get("jack") or {}
    if jack.get("driver") == "alsa":
        return "n%d" % jack.get("periods", 2)
    return jack.get("driver") or "dummy"


def set_of_document(doc, path):
    if doc.get("schema") != "omx-bench/1":
        raise NotADocument("%s is not an omx-bench/1 document" % path)
    rows = doc.get("scenarios") or []
    rates = {r["rate"] for r in rows if "rate" in r}
    frames = {r["frames"] for r in rows if "frames" in r}
    if len(rates) != 1 or len(frames) != 1:
        raise NotADocument("%s holds %d rates and %d frame counts, not one set" % (path, len(rates), len(frames)))
    rate, nframes = rates.pop(), frames.pop()
    hosts = {}
    for r in rows:
        if r.get("status") != "ok":
            continue
        h = hosts.setdefault(r["host"], {"ok": 0, "clean": 0, "xruns": 0})
        x = r.get("xruns") or 0
        h["ok"] += 1
        h["xruns"] += x
        if r.get("xruns") == 0:
            h["clean"] += 1
    ok = sum(h["ok"] for h in hosts.values())
    clean = sum(h["clean"] for h in hosts.values())
    return {"rate": rate, "frames": nframes, "periods": periods_of(doc), "ms": period_ms(rate, nframes),
            "id": doc.get("id", os.path.basename(path)), "hosts": hosts, "ok": ok,
            "xruns": sum(h["xruns"] for h in hosts.values()), "reachable": ok > 0, "clean": ok > 0 and clean == ok}


def unreachable_set(path, m):
    rate, frames, periods = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return {"rate": rate, "frames": frames, "periods": "n%d" % periods, "ms": period_ms(rate, frames),
            "id": os.path.basename(path), "hosts": {}, "ok": 0, "xruns": 0, "reachable": False, "clean": False}


def read(path):
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise NotADocument("%s is not JSON: %s" % (path, e))


def load_sets(paths):
    """one set per document, and one not-reachable set per set directory that holds no document"""
    sets = []
    for p in paths:
        if os.path.isdir(p):
            docs = sorted(os.path.join(p, n) for n in os.listdir(p) if n.endswith(".json"))
            if docs:
                sets += [set_of_document(read(d), d) for d in docs]
                continue
            m = SET_DIR.search(os.path.basename(os.path.normpath(p)))
            if not m:
                raise NotADocument("%s holds no document and is not a set directory r<rate>-f<frames>-n<periods>" % p)
            sets.append(unreachable_set(p, m))
        else:
            sets.append(set_of_document(read(p), p))
    return sets


def cell_of(s):
    return {"id": s["id"], "frames": s["frames"], "reachable": s["reachable"], "clean": s["clean"],
            "sub_ms": s["ms"] < 1.0, "xruns": s["xruns"], "hosts": {h: s["hosts"][h] for h in HOSTS if h in s["hosts"]}}


def report(sets):
    """{periods: {rates, rows, cells: {ms key: {rate: cell}}, safe: {rate: ms or None}}}"""
    out = {}
    for periods in sorted({s["periods"] for s in sets}):
        mine = [s for s in sets if s["periods"] == periods]
        rates = sorted({s["rate"] for s in mine})
        rows = sorted({s["ms"] for s in mine})
        cells = {}
        for s in mine:
            cells.setdefault(key(s["ms"]), {})[str(s["rate"])] = cell_of(s)
        safe = {}
        for rate in rates:
            best = None
            for s in sorted((s for s in mine if s["rate"] == rate), key=lambda s: -s["ms"]):
                if not s["clean"]:
                    break
                best = s["ms"]
            safe[str(rate)] = best
        out[periods] = {"rates": rates, "rows": rows, "cells": cells, "safe": safe}
    return out


def cell_text(c):
    if c is None:
        return "-"
    if not c["reachable"]:
        text = "not reachable (f%d)" % c["frames"]
    else:
        hosts = ", ".join("%s %d/%d%s" % (h, v["clean"], v["ok"], " (%d)" % v["xruns"] if v["xruns"] else "")
                          for h, v in c["hosts"].items())
        text = "%s f%d: %s" % ("clean" if c["clean"] else "xruns", c["frames"], hosts)
    return text + (" sub-ms" if c["sub_ms"] else "")


def markdown(rep):
    lines = []
    for periods, t in rep.items():
        lines += ["## %s" % periods, "",
                  "| period | %s |" % " | ".join(str(r) for r in t["rates"]),
                  "|---|%s|" % "|".join("---" for _ in t["rates"])]
        for ms in sorted(t["rows"], reverse=True):
            row = t["cells"].get(key(ms), {})
            lines.append("| %s ms | %s |" % (key(ms), " | ".join(cell_text(row.get(str(r))) for r in t["rates"])))
        lines.append("| safe minimum | %s |" % " | ".join(
            ("%s ms" % key(t["safe"][str(r)])) if t["safe"][str(r)] is not None else "none" for r in t["rates"]))
        lines.append("")
    lines.append("A cell: clean or xruns, its frames, then per host clean/ok and the xruns summed in brackets. The safe "
                 "minimum of a rate is its shortest clean period with every longer one clean.")
    return "\n".join(lines) + "\n"


def main(argv):
    as_json = "--json" in argv
    paths = [a for a in argv if a != "--json"]
    if not paths or any(a.startswith("-") for a in paths):
        sys.stderr.write("usage: matrix.py [--json] <document-or-set-directory>...\n")
        return 2
    try:
        rep = report(load_sets(paths))
    except (NotADocument, OSError) as e:
        sys.stderr.write("matrix: %s\n" % e)
        return 2
    sys.stdout.write(json.dumps(rep, indent=2) + "\n" if as_json else markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
