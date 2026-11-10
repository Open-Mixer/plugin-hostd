#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# tools/records-candidate.sh against stand-in apt-cache, dpkg, dnf and uname: a records package published for another
# architecture only is not in the channel for this one (plugin-hostd 0.20.1, trixie amd64: the arm64 build was
# read as a candidate and the full install check failed); one published for this architecture is.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
fail=0
mkdir -p "$t/bin"
cat > "$t/bin/apt-cache" <<'S'
#!/bin/bash
# a flat repository holding plugin-qualification-records for $ARCHES only
name=${2%%:*} arch=${2#*:}; [ "$arch" = "$2" ] && arch=
for a in $ARCHES; do
    if [ -z "$arch" ] || [ "$arch" = "$a" ]; then
        echo "$name:$a:"; echo "  Installed: (none)"; echo "  Candidate: 2026110901"; exit 0
    fi
done
echo "$name:"; echo "  Installed: (none)"; echo "  Candidate: (none)"
S
cat > "$t/bin/dpkg" <<'S'
#!/bin/bash
echo "$NATIVE_DEB"
S
cat > "$t/bin/dnf" <<'S'
#!/bin/bash
# repoquery: the package for each of $ARCHES, filtered by --arch when given
want=; while [ $# -gt 0 ]; do [ "$1" = --arch ] && { want=$2; shift; }; shift; done
for a in $ARCHES; do [ -z "$want" ] || [ "$want" = "$a" ] && echo "plugin-qualification-records-0:2026110901-1.fc44.$a"; done; true
S
cat > "$t/bin/uname" <<'S'
#!/bin/bash
echo "$NATIVE_RPM"
S
chmod +x "$t/bin/"*
check() { # label want kind native-deb native-rpm arches
    local got; got=$(PATH="$t/bin:$PATH" NATIVE_DEB=$4 NATIVE_RPM=$5 ARCHES=$6 bash "$here/tools/records-candidate.sh" "$3")
    if [ "$got" = "$2" ]; then echo "ok   $1"; else echo "FAIL $1: '$got', want '$2'"; fail=1; fi
}
check "deb: recommended, published for arm64 only, is not in the channel on amd64" "" deb amd64 x86_64 arm64
check "deb: published for amd64 is in the channel on amd64" 2026110901 deb amd64 x86_64 "arm64 amd64"
check "deb: published for arm64 is in the channel on arm64" 2026110901 deb arm64 aarch64 arm64
check "rpm: published for aarch64 only is not in the channel on x86_64" "" rpm amd64 x86_64 aarch64
check "rpm: published for x86_64 is in the channel on x86_64" "plugin-qualification-records-0:2026110901-1.fc44.x86_64" rpm amd64 x86_64 "aarch64 x86_64"
exit $fail
