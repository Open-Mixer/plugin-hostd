#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# make check-rendered against a stand-in omx-contract and pkg-config (#120): a release build is reproducible at its tag.
# The committed render records the omx-contract it was rendered with. A package build (RENDERED_COMPARE=recorded) judges
# the render only against that renderer: with a newer one installed it is not compared and says so, so a tag rebuilt
# after the channel moved on still builds; at the recorded renderer any drift is red. The default stays strict, so a
# development tree with a newer renderer is told to render again. make render-verbs writes the record.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
fail=0
record=include/plugin-hostd/plugin_hostd_vocabulary.h.rendered-with
mkdir -p "$t/bin" "$t/tree"
real_pc=$(command -v pkg-config)
cat > "$t/bin/pkg-config" <<S
#!/bin/bash
# omx-contract's version is \$RENDERER; every other question is the real pkg-config's
[ "\$*" = "--modversion omx-contract" ] && { echo "\$RENDERER"; exit 0; }
exec "$real_pc" "\$@"
S
cat > "$t/bin/omx-contract" <<'S'
#!/bin/bash
# render: --check reports a drift when $DRIFT=1; a write writes nothing
case " $* " in
  *" --check "*) if [ "${DRIFT:-0}" = 1 ]; then echo "omx-contract render --check: plugin_hostd_vocabulary.h differs"; exit 1; fi
                 echo "omx-contract render --target c --check: 1 files byte-identical"; exit 0 ;;
  *) echo "omx-contract render --target c: wrote 1 files"; exit 0 ;;
esac
S
chmod +x "$t/bin/"*
(cd "$here" && git ls-files -co --exclude-standard | tar -cf - -T -) | tar -xf - -C "$t/tree"
judge() { # label want-rc want-text renderer drift compare
    local rc=0 out
    out=$(cd "$t/tree" && RENDERER=$4 DRIFT=$5 make -s check-rendered PKG_CONFIG="$t/bin/pkg-config" \
          OMX_CONTRACT="$t/bin/omx-contract" ${6:+RENDERED_COMPARE=$6} 2>&1) || rc=$?
    if [ "$rc" = "$2" ] && grep -q -- "$3" <<< "$out"; then echo "ok   $1"
    else echo "FAIL $1: rc $rc (want $2), want '$3' in:"; sed 's/^/     /' <<< "$out"; fail=1; fi
}
echo 3.18.0 > "$t/tree/$record"
judge "package build at the recorded renderer, no drift: compared, green" 0 "byte-identical" 3.18.0 0 recorded
judge "package build at the recorded renderer, a drift: red" 2 "differs" 3.18.0 1 recorded
judge "package build with a newer renderer than the tag recorded: not compared, green" 0 \
      "rendered with omx-contract 3.18.0; 3.18.1 is installed: not compared" 3.18.1 1 recorded
judge "default (development) with a newer renderer and a drift: red" 2 "differs" 3.18.1 1 ""
rm -f "$t/tree/$record"
judge "package build with no record: compared, a drift red" 2 "differs" 3.18.1 1 recorded
rc=0; (cd "$t/tree" && RENDERER=3.18.1 make -s render-verbs PKG_CONFIG="$t/bin/pkg-config" OMX_CONTRACT="$t/bin/omx-contract" >/dev/null 2>&1) || rc=$?
if [ "$rc" = 0 ] && [ "$(cat "$t/tree/$record" 2>/dev/null)" = 3.18.1 ]; then echo "ok   render-verbs records the renderer"
else echo "FAIL render-verbs records the renderer: rc $rc, record '$(cat "$t/tree/$record" 2>/dev/null)'"; fail=1; fi
exit $fail
