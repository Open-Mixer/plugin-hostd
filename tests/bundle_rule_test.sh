#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# Which bundle an LV2 uri is, when several bundles of lv2_path name it: plugin-db's declared rule
# (PLUGIN_DB_BUNDLE_RULES, newest-version; OMX_PLUGIN_DB_BUNDLE_RULES_NEWEST_VERSION), lilv's. Of the bundles that
# realise the plugin, the one whose data gives it the highest lv2:minorVersion, then the highest lv2:microVersion, a
# version not stated counting as 0; of equal versions the first in the search path, its directories in order and the
# bundles of one directory in byte order of their names, never in the order the directory lists them (#57). Read
# through plugin-hostd --pin-files, which the add's pin check and plugin-qualify share: its "root" line.
set -u
daemon=${1:-./plugin-hostd}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failed=0
check() { if [ "$1" = 0 ]; then echo "ok   $2"; else echo "FAIL $2"; failed=1; fi; }
uri=urn:plugin-hostd:test:bundle-rule

# a bundle realising the plugin; its version, "<minor> <micro>" or empty for none, stated in the plugin's own TTL, which
# the manifest names with rdfs:seeAlso
bundle() {
    mkdir -p "$1"
    : > "$1/rule.so"
    cat > "$1/manifest.ttl" <<TTL
@prefix lv2:  <http://lv2plug.in/ns/lv2core#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<$uri> a lv2:Plugin ; lv2:binary <rule.so> ; rdfs:seeAlso <rule.ttl> .
TTL
    {
        echo '@prefix lv2: <http://lv2plug.in/ns/lv2core#> .'
        if [ -n "${2:-}" ]; then
            set -- "$1" $2
            echo "<$uri> a lv2:Plugin ; lv2:minorVersion $2 ; lv2:microVersion $3 ."
        else
            echo "<$uri> a lv2:Plugin ."
        fi
    } > "$1/rule.ttl"
}
root_of() {
    printf 'lv2_path %s\n' "$1" > "$work/conf"
    "$daemon" -c "$work/conf" --pin-files "$uri" 2>"$work/err" | sed -n 's/^root //p'
}

# 1. one directory whose listing order is not the byte order of two identical bundles' names: the byte-order first.
# The names are tried until the filesystem lists them otherwise than byte order (tmpfs lists the newest first, ext4 by
# a hash of the name)
found=
for k in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    dir=$work/order$k
    mkdir -p "$dir"
    bundle "$dir/m$k-a.lv2"
    bundle "$dir/m$k-b.lv2"
    listed=$(ls -f "$dir" | grep '\.lv2$' | head -1)
    if [ "$listed" != "m$k-a.lv2" ]; then
        found=$dir/m$k-a.lv2
        break
    fi
done
if [ -z "$found" ]; then
    check 1 "a directory listing two bundles otherwise than in byte order (none of 20 pairs)"
else
    got=$(root_of "$(dirname "$found")")
    [ "$got" = "$found" ]; check $? "of equal versions in one directory, the first in byte order of names ($(basename "$found")), not the one the directory lists first ($listed): got ${got:-none}"
fi

# 2. a newer version later on the path wins over an older one earlier; minor before micro; none stated is 0
first=$work/path1; second=$work/path2
bundle "$first/old.lv2" "0 1"
bundle "$second/new.lv2" "0 2"
got=$(root_of "$first:$second")
[ "$got" = "$second/new.lv2" ]; check $? "a higher lv2:microVersion later on the path wins over a lower one earlier: got ${got:-none}"
bundle "$first/old.lv2" "1 9"
bundle "$second/new.lv2" "2 0"
got=$(root_of "$first:$second")
[ "$got" = "$second/new.lv2" ]; check $? "a higher lv2:minorVersion wins over a higher lv2:microVersion: got ${got:-none}"
bundle "$first/old.lv2" ""
bundle "$second/new.lv2" "0 1"
got=$(root_of "$first:$second")
[ "$got" = "$second/new.lv2" ]; check $? "a version not stated counts as 0: got ${got:-none}"

# 3. equal versions in two directories: the earlier directory, though the later one's bundle sorts first by name
eq1=$work/eq1; eq2=$work/eq2
bundle "$eq1/zz.lv2" "0 3"
bundle "$eq2/aa.lv2" "0 3"
got=$(root_of "$eq1:$eq2")
[ "$got" = "$eq1/zz.lv2" ]; check $? "of equal versions in two directories, the earlier directory's, whatever its name: got ${got:-none}"

if [ $failed = 0 ]; then
    echo "ok   bundle rule: newest version, then search path and byte order, as plugin-db declares it"
fi
exit $failed
