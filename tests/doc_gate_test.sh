#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The documentation gates only shrink, by mechanism (tools/doc_shrink.sh, tools/doxygen_gate.sh --update). In a scratch
# git tree holding copies of the two scripts, a stand-in doxygen (it writes the warnings a file lists) and a Python file
# with a `# noqa`, the base branch is committed, then each arm changes the working tree and runs a script:
#   doc_shrink.sh: the tree as the base ok; a baseline line added, a noqa added: each red; a line removed ok; a base
#     the tree cannot read red, by name; a base without the gate (the change that brings it) ok;
#   doxygen_gate.sh --update: refused, the baseline untouched, when a warning is not in it; it lowers the baseline when
#     a listed warning is gone.
# Needs git and sh only; no doxygen, no ruff.
set -u
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failed=0
check() { if [ "$1" = 0 ]; then echo "ok   $2"; else echo "FAIL $2"; failed=1; fi; }

t=$work/tree
mkdir -p "$t/tools" "$t/src" "$t/clients"
cp "$here/tools/doxygen_gate.sh" "$t/tools/"
[ -f "$here/tools/doc_shrink.sh" ] && cp "$here/tools/doc_shrink.sh" "$t/tools/"
# the stand-in doxygen: each line of tools/warnings is a warning at line 1 of its file
cat > "$work/doxygen" <<'SH'
#!/bin/sh
sed 's/^\([^:]*\): /\1:1: warning: /' tools/warnings > "$DOXYGEN_LOG"
SH
chmod +x "$work/doxygen"
printf 'INPUT = src\n' > "$t/tools/Doxyfile"
printf 'src/a.h: Member A is not documented.\nsrc/a.h: Member B is not documented.\n' > "$t/tools/warnings"
cp "$t/tools/warnings" "$t/tools/doxygen.baseline"
printf '[lint]\nselect = ["D"]\n' > "$t/ruff.toml"
printf 'def f():  # noqa: D103\n    return 1\n' > "$t/clients/m.py"
(cd "$t" && git init -q -b main && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -qm base) || exit 1
export DOXYGEN="$work/doxygen" DOC_GATE_BASE=main DOC_GATE_PY=clients

shrink() { (cd "$t" && sh tools/doc_shrink.sh) > "$work/out" 2>&1; }
# red_by <text> <command...>: the command fails and its output names <text>
red_by() { want=$1; shift; if "$@"; then return 1; fi; grep -q -- "$want" "$work/out"; }
reset() { (cd "$t" && git checkout -q -- . && git clean -qfd); }

shrink; check $? "doc_shrink: the tree as the base"
echo "src/a.h: Member C is not documented." >> "$t/tools/doxygen.baseline"
red_by "tools/doxygen.baseline" shrink; check $? "doc_shrink: a baseline line added is red, by name"
reset
printf 'def g():  # noqa: D103\n    return 2\n' >> "$t/clients/m.py"
red_by "noqa" shrink; check $? "doc_shrink: a noqa added is red, by name"
reset
sed -i '1d' "$t/tools/doxygen.baseline"
shrink; check $? "doc_shrink: a baseline line removed"
reset
DOC_GATE_BASE=no-such-base red_by "no-such-base" shrink; check $? "doc_shrink: a base it cannot read is red, by name"
(cd "$t" && git checkout -q -b bare main && git rm -q tools/doxygen.baseline ruff.toml && git -c user.name=t -c user.email=t@t commit -qm bare && git checkout -q main)
DOC_GATE_BASE=bare shrink; check $? "doc_shrink: a base without the gate (the change that brings it)"

echo "src/a.h: Member C is not documented." >> "$t/tools/warnings"
update() { (cd "$t" && sh tools/doxygen_gate.sh --update) > "$work/out" 2>&1; }
red_by "doxygen-gate: --update only lowers the baseline" update && [ "$(wc -l < "$t/tools/doxygen.baseline")" = 2 ]
check $? "--update refuses a warning the baseline does not list, by name, and leaves the baseline"
reset
sed -i '1d' "$t/tools/warnings"
update && [ "$(wc -l < "$t/tools/doxygen.baseline")" = 1 ]; check $? "--update lowers the baseline when a listed warning is gone"
reset

[ "$failed" = 0 ] || { echo "--- last output:"; cat "$work/out"; exit 1; }
echo "ok   the documentation gates only shrink"
