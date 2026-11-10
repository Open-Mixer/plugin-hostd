#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# plugin-hostd-full installed from the channel in a clean Debian or Fedora container, the way the install pages say:
#
#   tools/full-install-check.sh deb|rpm <version> default|headless
#
# default   apt-get install plugin-hostd-full / dnf install plugin-hostd-full: every package of the stack is installed,
#           omx-panel with it (a Recommends, a weak dependency).
# headless  apt-get install --no-install-recommends / dnf install --setopt=install_weak_deps=False: the same stack with
#           no omx-panel, no X server, no Xlib, Wayland or GTK. Two pulls remain that the panel is not behind, and the
#           check names who pulls them so a new one is red: libxcb (the X protocol client library) only for
#           omx-clap-host, which links it to embed a plugin's window; nodejs only for plugin-qualify and omx-contract
#           (and Debian's node-* modules of nodejs itself).
# Both: plugin-hostd is <version>, and plugin-qualification-records is the build of this machine's architecture,
# holding the sets of its class (rpi5 on arm64/aarch64, x86-64 on amd64/x86_64). The channel must already be configured (add-openmixer); Pages
# serves a fresh publish a little late, so the install is retried before it is called broken.
set -euo pipefail

kind=$1 ver=${2#v} mode=$3
STACK="plugin-hostd plugin-hostd-full omx-clap-host omx-plugins plugin-qualify"
X_DEB="libx11-6 libwayland-client0 libgtk-3-0 libgtk-4-1 xserver-common xserver-xorg-core"
X_RPM="libX11 libwayland-client gtk3 gtk4 xorg-x11-server-common xorg-x11-server-Xorg"
# who may pull what headless (see above)
XCB_BY="omx-clap-host"
NODE_BY="plugin-qualify omx-contract"
fail() { echo "::error::plugin-hostd-full $ver ($kind, $mode): $*"; exit 1; }

case $mode in default|headless) ;; *) echo "default or headless, not $mode" >&2; exit 2 ;; esac
machine=$(uname -m)
case $machine in
    x86_64) class=x86-64 ;;
    aarch64) class=rpi5 ;;
    *) fail "no records class for $machine" ;;
esac

ok=
for try in $(seq 1 "${TRIES:-20}"); do
    case $kind in
        deb)
            apt-get update -qq || true
            pinned=$(apt-cache madison plugin-hostd-full | awk -v v="$ver" '$3 ~ "^"v"[-~+]" || $3 == v {print $3; exit}')
            opt=()
            [ "$mode" = headless ] && opt=(--no-install-recommends)
            if [ -n "$pinned" ] && apt-get install -y "${opt[@]}" "plugin-hostd-full=$pinned"; then ok=1; break; fi ;;
        rpm)
            dnf clean expire-cache -q || true
            opt=()
            [ "$mode" = headless ] && opt=(--setopt=install_weak_deps=False)
            if dnf install -y "${opt[@]}" "plugin-hostd-full-$ver"; then ok=1; break; fi ;;
        *) echo "deb or rpm, not $kind" >&2; exit 2 ;;
    esac
    echo "attempt $try: plugin-hostd-full $ver is not installable yet"; sleep "${WAIT:-30}"
done
[ -n "$ok" ] || fail "does not install"

installed() {
    if [ "$kind" = deb ]; then dpkg-query -W -f '${Status}' "$1" 2>/dev/null | grep -q 'install ok installed'
    else rpm -q "$1" >/dev/null 2>&1; fi
}
version_of() {
    if [ "$kind" = deb ]; then dpkg-query -W -f '${Version}' "$1"; else rpm -q --qf '%{VERSION}' "$1"; fi
}

for p in $STACK; do
    installed "$p" || fail "$p is not installed"
    echo "installed: $p $(version_of "$p")"
done
for p in plugin-hostd plugin-hostd-full; do
    case $(version_of "$p") in "$ver"|"$ver"-*|"$ver"~*|"$ver"+*) ;; *) fail "$p is $(version_of "$p"), not $ver" ;; esac
done

# plugin-qualification-records: one package, built per architecture; the one installed is this machine's, and holds
# the sets of this machine's class
# (recommended until the package is in the channel: required in a default install once the channel has it, checked
# whenever it is installed)
records=plugin-qualification-records
# in the channel means a candidate for this machine's architecture (tools/records-candidate.sh)
have=$(bash "$(dirname "$0")/records-candidate.sh" "$kind" "$records")
if [ "$mode" = default ] && [ -n "$have" ]; then installed "$records" || fail "$records, recommended and in the channel, is not installed"; fi
if ! installed "$records"; then
    echo "records: $records not installed (${have:-not in the channel})"
else
if [ "$kind" = deb ]; then
    rarch=$(dpkg-query -W -f '${Architecture}' "$records"); want=$(dpkg --print-architecture)
else
    rarch=$(rpm -q --qf '%{ARCH}' "$records"); want=$machine
fi
[ "$rarch" = "$want" ] || fail "$records is built for $rarch, this machine is $want"
d=/usr/share/omx/qualification/$class
[ -n "$(ls -A "$d" 2>/dev/null)" ] || fail "$records $(version_of "$records") holds no set under $d"
echo "records: $records $(version_of "$records") ($rarch): $(ls "$d" | tr '\n' ' ')"
fi

if [ "$mode" = default ]; then
    installed omx-panel || fail "omx-panel, recommended, is not installed"
    echo "installed: omx-panel $(version_of omx-panel)"
    exit 0
fi

installed omx-panel && fail "omx-panel is installed headless"
echo "headless: no omx-panel"
x=$([ "$kind" = deb ] && echo "$X_DEB" || echo "$X_RPM")
for p in $x; do installed "$p" && fail "$p (X or GUI) is installed headless"; done
echo "headless: none of $x"
# the packages of this install that require $1 (the deb or rpm name of a library or tool)
required_by() {
    if [ "$kind" = deb ]; then
        apt-cache rdepends --installed --no-recommends --no-suggests "$1" | sed -n '3,$p' | sed 's/^ *|*//' | sort -u
    else
        { rpm -q --whatrequires "$1" --qf '%{NAME}\n'
          for c in $(rpm -q --provides "$1" | awk '{print $1}'); do rpm -q --whatrequires "$c" --qf '%{NAME}\n'; done
          for f in $(rpm -ql "$1" 2>/dev/null | grep -E '\.so\.[0-9]+$|/bin/'); do
            rpm -q --whatrequires "$(basename "$f")()(64bit)" --qf '%{NAME}\n'; rpm -q --whatrequires "$f" --qf '%{NAME}\n'; done
          true; } 2>/dev/null |
            grep -v '^no package' | sort -u
    fi
}
only_by() {
    local what=$1 allowed=$2 by p
    # an RPM capability is provided under another name at times (nodejs by nodejs22): the package that provides it
    if [ "$kind" = rpm ] && rpm -q --whatprovides "$what" >/dev/null 2>&1; then
        what=$(rpm -q --whatprovides "$what" --qf '%{NAME}\n' | head -1)
    fi
    installed "$what" || { echo "headless: no $1"; return 0; }
    # a query that finds no requirer exits 1: the list is what it printed
    by=$(required_by "$what" || true)
    echo "headless: $what is required by: $(echo $by)"
    for p in $by; do
        # a library package requires its own sonames
        [ "$p" = "$what" ] && continue
        case " $allowed " in *" $p "*) continue ;; esac
        case $p in node-*|nodejs*) [ "$1" = nodejs ] && continue ;; esac
        installed "$p" && fail "$what is pulled by $p, which is not one of: $allowed"
    done
}
only_by "$([ "$kind" = deb ] && echo libxcb1 || echo libxcb)" "$XCB_BY"
only_by nodejs "$NODE_BY"
echo "headless: plugin-hostd-full $ver ($kind) holds"
