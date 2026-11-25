# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-hostd-probe describe is held to omx-contract's one rule for a scanned CLAP parameter's kind (omx-contract
# docs/descriptors.md, "A scanned CLAP parameter's kind"): the vectors the installed omx-contract ships,
# share/omx-contract/clap-kind-vectors.json, are run through describe one by one, each as the field dump omx-clap-scan
# would write for a plugin with that one parameter (its flags, range and default; a value text per whole step when the
# vector has points; a contract entry when it has one), and the descriptor's control must carry the kind the vector
# expects, a toggle's default and a travel's scale with it. The rule is never restated here: the table is the test.
# Sabotage (src/describe.c put_control): drop the range check and `stepped-0-to-2` reads a toggle; drop the step check and
# `contract-step-half` does; drop the rule and `toggle-off` stays a travel; read the default as non-zero and
# `toggle-default-below-half` turns on.
#   describe_clap_kind_vectors_test.py   PROBE is the runner (default ./plugin-hostd-probe); the vectors file is
#   $OMX_CONTRACT_KIND_VECTORS (a checkout's, standing in for the install), else the installed omx-contract's data
#   directory's; none is a failure that names it (the file ships from omx-contract 3.19.0, Open-Mixer/omx-contract#67).
import json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from describe_test import check, describe, scratch  # noqa: E402
import describe_test  # noqa: E402
TARGET = "clap:kind.clap#org.openmixer.test.kind"


def vectors_path():
    env = os.environ.get("OMX_CONTRACT_KIND_VECTORS")
    if env:
        return env
    datadir = subprocess.run([os.environ.get("PKG_CONFIG", "pkg-config"), "--variable=datadir", "omx-contract"],
                             capture_output=True, text=True).stdout.strip()
    return os.path.join(datadir or "/usr/share/omx-contract", "clap-kind-vectors.json")


def number(v):
    return "%.17g" % v if isinstance(v, float) and not v.is_integer() else "%d" % v


def dump_of(v):
    """the field dump omx-clap-scan writes for a plugin whose one parameter is the vector's input, in the scanner's
    order: clap_param_info's fields, then the texts, then the contract entry's"""
    i = v["input"]
    rows = [("plugin", "clap_entry", "kind.clap"), ("plugin", "clap_plugin_descriptor.id", "org.openmixer.test.kind"),
            ("plugin", "clap_plugin_descriptor.name", "kind"), ("plugin", "clap_plugin_descriptor.vendor", "test"),
            ("plugin", "clap_plugin_descriptor.version", "1"), ("plugin", "clap_plugin.get_extension", "CLAP_EXT_PARAMS"),
            ("plugin", "clap_plugin.get_extension", "CLAP_EXT_AUDIO_PORTS")]
    if i["contract"] is not None:
        rows.append(("plugin", "clap_plugin.get_extension", "org.openmixer.param-contract/1"))
    rows += [("param:0", "clap_param_info.id", "0"), ("param:0", "clap_param_info.name", "p"),
             ("param:0", "clap_param_info.min_value", number(i["min"])), ("param:0", "clap_param_info.max_value", number(i["max"])),
             ("param:0", "clap_param_info.default_value", number(i["default"]))]
    rows += [("param:0", "clap_param_info.flags", f) for f in i["flags"]]
    if i["points"]:
        rows += [("param:0", "clap_plugin_params.value_to_text", "%d text%d" % (k, k)) for k in range(int(i["min"]), int(i["max"]) + 1)]
    if i["contract"] is not None:
        rows.append(("param:0", "omx_clap_param_contract_entry.symbol", "p"))
        rows.append(("param:0", "omx_clap_param_contract_entry.scale", i["contract"]["scale"]))
        if "step" in i["contract"]:
            rows.append(("param:0", "omx_clap_param_contract_entry.step", number(i["contract"]["step"])))
    for d, n in (("audio_in", "in"), ("audio_out", "out")):
        rows += [("%s:0" % d, "clap_audio_port_info.id", "0"), ("%s:0" % d, "clap_audio_port_info.name", n),
                 ("%s:0" % d, "clap_audio_port_info.channel_count", "2"), ("%s:0" % d, "clap_audio_port_info.flags", "CLAP_AUDIO_PORT_IS_MAIN"),
                 ("%s:0" % d, "clap_audio_port_info.port_type", "CLAP_PORT_STEREO")]
    return "# omx-clap-scan --fields 1\n" + "".join("\t".join(r) + "\n" for r in rows)


def main():
    path = vectors_path()
    if not os.path.exists(path):
        check(False, "omx-contract's clap-kind-vectors.json is at %s: the kind rule's vectors ship from omx-contract 3.19.0 "
              "(Open-Mixer/omx-contract#67); install it, or set OMX_CONTRACT_KIND_VECTORS to a checkout's" % path)
        print("describe_clap_kind_vectors: 1 failure(s)")
        return 1
    with open(path) as f:
        vectors = json.load(f)["vectors"]
    check(len(vectors) >= 16, "the vectors file holds the table (%d vectors)" % len(vectors))
    with tempfile.TemporaryDirectory() as tmp:
        for v in vectors:
            r = describe(TARGET, dump=scratch(tmp, v["name"] + ".tsv", dump_of(v)))
            if r.returncode != 0:
                check(False, "%s: describe exits 0: %s" % (v["name"], r.stderr.strip()))
                continue
            c = json.loads(r.stdout)["controls"][0]
            e = v["expect"]
            got = {"kind": c.get("kind")}
            if "default" in e:
                got["default"] = c.get("default")
            if "scale" in e:
                got["scale"] = c.get("travel", {}).get("scale")
            check(got == e, "%s: %s reads %s" % (v["name"], json.dumps(v["input"]), json.dumps(e))
                  + ("" if got == e else "; describe says %s" % json.dumps(got)))
    failed = describe_test.failed
    print("describe_clap_kind_vectors: %d failure(s)" % failed if failed else "describe_clap_kind_vectors: held, %d vectors" % len(vectors))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
