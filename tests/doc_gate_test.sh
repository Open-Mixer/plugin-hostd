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
#     a listed warning is gone;
#   doxygen_gate.sh: the tree as the base ok; a tracked header of the Doxyfile's INPUT with no @file in a doc comment
#     red, by name (doxygen reports a file's undocumented members only when the file has @file); a doxygen that writes
#     no warning log red, by name; a header doxygen wrote no page for (it did not read it) red, by name; a doxygen of
#     another version than tools/doxygen.version pins red, both versions named.
# Last, the repository's own tools/Doxyfile under the real doxygen (DOXYGEN_REAL, doxygen by default; the doc-gates job
# installs it, and its absence is red, by name): a header whose one function documents its parameters and its return
# gives no warning, so a fully documented header can empty the baseline; with its @return dropped it warns (doxygen did
# read it). No ruff needed.
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
# the stand-in doxygen: each line of tools/warnings is a warning at line 1 of its file, and each src/*.h gets its HTML
# page, named as doxygen names it (a.h: a_8h.html). An arm's file changes it: tools/standin-version (the version it
# answers, 1.9.8 without), tools/standin-nolog (it writes no log), tools/standin-nopage (the headers it gives no page)
cat > "$work/doxygen" <<'SH'
#!/bin/sh
if [ "${1:-}" = "--version" ]; then cat tools/standin-version 2>/dev/null || echo 1.9.8; exit 0; fi
[ -f tools/standin-nolog ] || sed 's/^\([^:]*\): /\1:1: warning: /' tools/warnings > "$DOXYGEN_LOG"
mkdir -p "$DOXYGEN_OUT/html"
for h in src/*.h; do
    [ -f "$h" ] || continue
    grep -qx "$h" tools/standin-nopage 2>/dev/null && continue
    : > "$DOXYGEN_OUT/html/$(basename "$h" .h | sed 's/_/__/g')_8h.html"
done
SH
chmod +x "$work/doxygen"
printf 'INPUT = src\nFILE_PATTERNS = *.h\n' > "$t/tools/Doxyfile"
echo 1.9.8 > "$t/tools/doxygen.version"
printf '/** @file\n * @brief A header.\n */\nint A;\nint B;\n' > "$t/src/a.h"
printf 'src/a.h: Member A is not documented.\nsrc/a.h: Member B is not documented.\n' > "$t/tools/warnings"
cp "$t/tools/warnings" "$t/tools/doxygen.baseline"
printf '[lint]\nselect = ["D"]\n' > "$t/ruff.toml"
printf 'def f():  # noqa: D103\n    return 1\n' > "$t/clients/m.py"
(cd "$t" && git init -q -b main && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -qm base) || exit 1
export DOXYGEN="$work/doxygen" DOC_GATE_BASE=main DOC_GATE_PY=clients

shrink() { (cd "$t" && sh tools/doc_shrink.sh) > "$work/out" 2>&1; }
# red_by <text> <command...>: the command fails and its output names <text>
red_by() { want=$1; shift; if "$@"; then return 1; fi; grep -q -- "$want" "$work/out"; }
reset() { (cd "$t" && git reset -q --hard && git clean -qfd); }

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
DOC_GATE_BASE='' red_by "DOC_GATE_BASE is empty" shrink; check $? "doc_shrink: an empty base is red, by name, never a default"
DOC_GATE_BASE=origin/ red_by "origin/" shrink; check $? "doc_shrink: a base with no branch (origin/) is red, by name"
# A remote base is fetched before it is read: a remote-tracking ref is a copy from the last fetch, and a stale one can
# already hold the rows this change grows. The upstream here holds the base; origin/main in the clone is stale and
# carries one more baseline line, as the tree does.
up="$work/up"; git clone -q --bare "$t" "$up"
(cd "$t" && git remote add origin "$up" && git checkout -q -b stale main && echo "src/a.h: Member D is not documented." >> tools/doxygen.baseline \
    && git -c user.name=t -c user.email=t@t commit -qam stale && git update-ref refs/remotes/origin/main stale && git checkout -q main && git branch -qD stale)
echo "src/a.h: Member D is not documented." >> "$t/tools/doxygen.baseline"
DOC_GATE_BASE=origin/main red_by "tools/doxygen.baseline grew" shrink; check $? "doc_shrink: a remote base is fetched, never read stale (the stale ref holds the grown line)"
reset
(cd "$t" && git update-ref refs/remotes/origin/main main && git remote set-url origin "$work/gone")
DOC_GATE_BASE=origin/main red_by "could not fetch origin/main" shrink; check $? "doc_shrink: a remote base it cannot fetch is red, by name, never the stale ref"
(cd "$t" && git remote remove origin)
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

gate() { (cd "$t" && sh tools/doxygen_gate.sh) > "$work/out" 2>&1; }
gate; check $? "doxygen_gate: the tree as the base"
printf 'int C;\n' > "$t/src/b.h"
(cd "$t" && git add src/b.h)
red_by "src/b.h has no @file" gate; check $? "doxygen_gate: a tracked header with no @file is red, by name"
reset
printf '/* @file not a doc comment */\nint C;\n' > "$t/src/b.h"
(cd "$t" && git add src/b.h)
red_by "src/b.h has no @file" gate; check $? "doxygen_gate: an @file outside a /** doc comment is red, by name"
reset
: > "$t/tools/standin-nolog"
red_by "wrote no warning log" gate; check $? "doxygen_gate: a doxygen that writes no warning log is red, by name"
reset
echo src/a.h > "$t/tools/standin-nopage"
red_by "no page for src/a.h" gate; check $? "doxygen_gate: a header doxygen wrote no page for is red, by name"
reset
echo 1.18.0 > "$t/tools/standin-version"
red_by "doxygen is 1.18.0, tools/doxygen.version pins 1.9.8" gate
check $? "doxygen_gate: a doxygen of another version is red, both versions named"
reset

r=$work/real
mkdir -p "$r/tools" "$r/src"
cp "$here/tools/doxygen_gate.sh" "$here/tools/doxygen.version" "$r/tools/"
# every setting of the repository's Doxyfile, read where this tree's header is
printf '@INCLUDE = %s/tools/Doxyfile\nINPUT = src\n' "$here" > "$r/tools/Doxyfile"
: > "$r/tools/doxygen.baseline"
printf '/** @file\n * @brief A header.\n */\n\n/**\n * @brief The sum.\n * @param a One addend.\n * @param b The other.\n * @return a + b.\n */\nint add(int a, int b);\n' > "$r/src/a.h"
# the gate reads the tracked headers
(cd "$r" && git init -q -b main && git add -A) || exit 1
real=${DOXYGEN_REAL:-doxygen}
if command -v "$real" >/dev/null 2>&1; then
    (cd "$r" && DOXYGEN=$real sh tools/doxygen_gate.sh) > "$work/out" 2>&1
    check $? "the real doxygen with tools/Doxyfile: a fully documented function gives no warning"
    # and doxygen read it: the same header with its @return dropped warns, by the function's name
    sed -i '/@return/d' "$r/src/a.h"
    # shellcheck disable=SC2016 # the inner sh expands them
    red_by "return type of member add" sh -c 'cd "$1" && DOXYGEN=$2 sh tools/doxygen_gate.sh > "$3" 2>&1' sh "$r" "$real" "$work/out"
    check $? "the real doxygen reads the header: its @return dropped warns, by name"
else
    echo "doxygen ($real) is not installed" > "$work/out"
    check 1 "the real doxygen with tools/Doxyfile: $real is not installed"
fi

[ "$failed" = 0 ] || { echo "--- last output:"; cat "$work/out"; exit 1; }
echo "ok   the documentation gates only shrink"
