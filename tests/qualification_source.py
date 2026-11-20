# SPDX-License-Identifier: GPL-3.0-or-later
# Where the tests find the qualification domain, the document plugin-hostd owns
# (contract.d/qualification/qualification.json of this tree): the first directory of $OMX_CONTRACT_PATH (a ':' list)
# that holds it, else this checkout's contract.d, else the installed contract directory (pkg-config omx-contract). A test that changes a word writes a
# scratch copy with fixture() and points the loader at it; the source is never edited.
import json, os, shutil, subprocess

PKG_CONFIG = os.environ.get("PKG_CONFIG", "pkg-config")
DOMAIN = "qualification"


def search_path():
    listed = [d for d in os.environ.get("OMX_CONTRACT_PATH", "").split(":") if d]
    installed = subprocess.run([PKG_CONFIG, "--variable=contractdir", "omx-contract"], capture_output=True, text=True).stdout.strip()
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contract.d")
    return listed + [here] + ([installed] if installed else [])


def source_dir():
    """the contract directory that holds the qualification domain"""
    for d in search_path():
        if os.path.exists(os.path.join(d, DOMAIN, DOMAIN + ".json")):
            return d
    raise SystemExit("the qualification domain is in none of %s: install plugin-hostd-contract, or put a checkout's "
                     "contract.d in OMX_CONTRACT_PATH" % (search_path(),))


def document():
    with open(os.path.join(source_dir(), DOMAIN, DOMAIN + ".json")) as f:
        return json.load(f)


def fixture(root, edit=None, name="fixture"):
    """a scratch contract directory root/<name> holding the domain, its catalogs, and edit(document) applied; its path"""
    out = os.path.join(root, name)
    shutil.copytree(os.path.join(source_dir(), DOMAIN), os.path.join(out, DOMAIN))
    doc = document()
    if edit:
        edit(doc)
    with open(os.path.join(out, DOMAIN, DOMAIN + ".json"), "w") as f:
        json.dump(doc, f, indent=2)
    return out


def words(item):
    return [e["const"] for e in document()["components"]["schemas"][item]["oneOf"]]


def rename_word(item, old, new):
    def edit(doc):
        for e in doc["components"]["schemas"][item]["oneOf"]:
            if e["const"] == old:
                e["const"] = new
                return
        raise SystemExit("%s has no word %s" % (item, old))
    return edit
