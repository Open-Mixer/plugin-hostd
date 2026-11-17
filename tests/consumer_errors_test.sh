#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# make test-consumer installs the protocol package into a scratch prefix and builds tests/consumer.c against it through
# pkg-config. When the installed plugin-hostd.pc's Requires: are not met (a floor no installed package reaches), the
# failure must say so: pkg-config's own reason, and a FAIL line naming the step, never a bare make error. A pkg-config
# stand-in refuses `--exists plugin-hostd` with a reason it prints only when asked (--print-errors), as pkg-config does;
# everything else goes to the real one.
set -u
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
real=$(command -v "${PKG_CONFIG:-pkg-config}")
cat > "$work/pkg-config" <<SH
#!/bin/sh
case " \$* " in
*" --exists "*"plugin-hostd "*)
    case " \$* " in *" --print-errors "*) echo "Package 'plugin-hostd-protocol' has version '0.0.1', required version is '>= 99.0'" >&2 ;; esac
    exit 1 ;;
esac
exec "$real" "\$@"
SH
chmod +x "$work/pkg-config"
out=$(make -s test-consumer PKG_CONFIG="$work/pkg-config" 2>&1)
rc=$?
failed=0
check() { if [ "$1" = 0 ]; then echo "ok   $2"; else echo "FAIL $2"; failed=1; fi; }
[ "$rc" != 0 ]; check $? "test-consumer fails when plugin-hostd.pc's Requires: are not met (rc $rc)"
printf '%s\n' "$out" | grep -qF "required version is '>= 99.0'"; check $? "it prints pkg-config's own reason"
printf '%s\n' "$out" | grep -q "^FAIL test-consumer: pkg-config --exists plugin-hostd"; check $? "it names the step that failed"
[ "$failed" = 0 ] || { printf '%s\n' "$out" | tail -5; exit 1; }
echo "ok   test-consumer names its failing step and pkg-config's reason"
