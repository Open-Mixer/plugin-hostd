#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# make test-consumer installs the protocol package into a scratch prefix and builds tests/consumer.c against it through
# pkg-config. Each of its four steps that fails must say so by name, never a bare make error; the pkg-config step also
# prints pkg-config's own reason (an unmet Requires: of the installed plugin-hostd.pc). One arm per step, each breaking
# only that step through a stand-in:
#   install    an `install` first on PATH that fails, so the install into the scratch prefix fails;
#   pkg-config one that refuses `--exists plugin-hostd` with a reason it prints only when asked (--print-errors), as
#              pkg-config does; everything else goes to the real one;
#   build      a CC that fails on tests/consumer.c and compiles everything else;
#   run        a CC that builds tests/consumer.c as a program that exits 3.
# MAKE is the make that runs this (the Makefile passes $(MAKE)).
set -u
make=${MAKE:-make}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
real_pc=$(command -v "${PKG_CONFIG:-pkg-config}")
real_cc=$(command -v "${CC:-cc}")
mkdir "$work/bin"

cat > "$work/bin/install" <<'SH'
#!/bin/sh
echo "install: refused (test stand-in)" >&2
exit 1
SH
cat > "$work/pkg-config" <<SH
#!/bin/sh
case " \$* " in
*" --exists "*"plugin-hostd "*)
    case " \$* " in *" --print-errors "*) echo "Package 'plugin-hostd-protocol' has version '0.0.1', required version is '>= 99.0'" >&2 ;; esac
    exit 1 ;;
esac
exec "$real_pc" "\$@"
SH
# the CC stand-ins: anything but tests/consumer.c goes to the real compiler
for mode in build run; do
cat > "$work/cc-$mode" <<SH
#!/bin/sh
case " \$* " in *" tests/consumer.c "*) ;; *) exec "$real_cc" "\$@" ;; esac
[ "$mode" = build ] && { echo "tests/consumer.c: refused (test stand-in)" >&2; exit 1; }
out=
while [ \$# -gt 0 ]; do [ "\$1" = -o ] && out=\$2; shift; done
printf 'int main(void) { return 3; }\n' | "$real_cc" -x c - -o "\$out"
SH
done
chmod +x "$work/bin/install" "$work/pkg-config" "$work/cc-build" "$work/cc-run"

failed=0
check() { if [ "$1" = 0 ]; then echo "ok   $2"; else echo "FAIL $2"; failed=1; fi; }
# arm <name> <the FAIL line's text after "FAIL test-consumer: "> <command>: test-consumer fails and names that step
arm() {
    name=$1 want=$2; shift 2
    out=$("$@" 2>&1); rc=$?
    [ "$rc" != 0 ]; check $? "$name: test-consumer fails (rc $rc)"
    printf '%s\n' "$out" | grep -qF "FAIL test-consumer: $want"; check $? "$name: it names the step ($want)"
}
arm install "make install_protocol into a scratch prefix" env PATH="$work/bin:$PATH" "$make" -s test-consumer
arm pkg-config "pkg-config --exists plugin-hostd" "$make" -s test-consumer PKG_CONFIG="$work/pkg-config"
printf '%s\n' "$out" | grep -qF "required version is '>= 99.0'"; check $? "pkg-config: it prints pkg-config's own reason"
arm build "tests/consumer.c against the installed headers and library" "$make" -s test-consumer CC="$work/cc-build"
arm run "the consumer built against the installed package" "$make" -s test-consumer CC="$work/cc-run"
[ "$failed" = 0 ] || exit 1
echo "ok   test-consumer names each failing step, and pkg-config's reason"
