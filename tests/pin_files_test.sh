#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# plugin-hostd --pin-files <uri>: the files a pin of the plugin holds, as an add collects them (pins_check). A copy of
# the LV2 fixture bundle whose manifest also names a presets file for the plugin, as mda Piano's and Surge XT's do: the
# presets file is listed, the bundle's file named for another plugin only is not, a plugin in no bundle exits 1 with
# its reason, and a CLAP uri lists its .clap file. plugin-qualify takes the list from here (plugin-qualify#228).
set -u
daemon=${1:-./plugin-hostd}
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failed=0
check() { if [ "$1" = 0 ]; then echo "ok   $2"; else echo "FAIL $2"; failed=1; fi; }

bundle=$work/lv2/presets-fixture.lv2
mkdir -p "$bundle"
cp "$here/plugin-hostd-fixture.lv2/plugin-hostd-fixture.ttl" "$bundle/"
: > "$bundle/plugin-hostd-fixture.so"
: > "$bundle/presets.ttl"
: > "$bundle/other.ttl"
cat > "$bundle/manifest.ttl" <<'TTL'
@prefix lv2:  <http://lv2plug.in/ns/lv2core#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<urn:plugin-hostd:test:gain> a lv2:Plugin ; lv2:binary <plugin-hostd-fixture.so> ;
    rdfs:seeAlso <plugin-hostd-fixture.ttl> , <presets.ttl> .
<urn:plugin-hostd:test:other> a lv2:Plugin ; lv2:binary <plugin-hostd-fixture.so> ; rdfs:seeAlso <other.ttl> .
TTL
printf 'lv2_path %s\n' "$work/lv2" > "$work/conf"

out=$("$daemon" -c "$work/conf" --pin-files urn:plugin-hostd:test:gain); rc=$?
want="root $bundle
file manifest.ttl
file plugin-hostd-fixture.so
file plugin-hostd-fixture.ttl
file presets.ttl"
[ $rc -eq 0 ] && [ "$out" = "$want" ]; check $? "an LV2 plugin: the manifest, its binary and every file the manifest names for it, presets.ttl included, and not other.ttl"
[ $rc -eq 0 ] || echo "$out" | sed 's/^/     /'

"$daemon" -c "$work/conf" --pin-files urn:plugin-hostd:test:absent >/dev/null 2>"$work/err"; rc=$?
[ $rc -eq 1 ] && grep -q 'in no bundle of lv2_path' "$work/err"; check $? "a plugin in no bundle exits 1 with the collector's reason ($rc: $(cat "$work/err"))"

# a manifest that names the plugin by a prefixed name (mda-lv2's, mod-mda-Piano's, whose uri is
# http://example.org/mda/Piano): the bundle is found, and a lookalike (mdap:Piano, mda:PianoRes) is no match
pbundle=$work/lv2/prefixed-fixture.lv2
mkdir -p "$pbundle"
: > "$pbundle/Piano.so"
: > "$pbundle/Piano.ttl"
: > "$pbundle/presets.ttl"
cat > "$pbundle/manifest.ttl" <<'TTL'
@prefix lv2:  <http://lv2plug.in/ns/lv2core#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix mda:  <http://example.org/mda/> .
@prefix mdap: <http://example.org/mda/presets#> .
mda:Piano a lv2:Plugin ; rdfs:seeAlso <Piano.ttl> ; lv2:binary <Piano.so> .
mdap:Piano-plain a <http://lv2plug.in/ns/ext/presets#Preset> ; lv2:appliesTo mda:Piano ; rdfs:seeAlso <presets.ttl> .
mda:PianoRes a lv2:Plugin ; lv2:binary <Piano.so> .
TTL
out=$("$daemon" -c "$work/conf" --pin-files http://example.org/mda/Piano); rc=$?
want="root $pbundle
file manifest.ttl
file Piano.ttl
file Piano.so"
[ $rc -eq 0 ] && [ "$out" = "$want" ]; check $? "an LV2 plugin the manifest names by a prefixed name is found: its binary and files, not the preset subject's (rc $rc)"
[ "$out" = "$want" ] || echo "$out" | sed 's/^/     /'

"$daemon" -c "$work/conf" --pin-files http://example.org/mda/Pian >/dev/null 2>"$work/err"; rc=$?
[ $rc -eq 1 ] && grep -q 'in no bundle of lv2_path' "$work/err"; check $? "a name that is only the start of a prefixed name is in no bundle ($rc)"

# a manifest with a leading UTF-8 BOM before its first @prefix (TAL-NoiseMaker's, Vitalium's both ship one): unskipped,
# the BOM glues onto "@prefix" so it is read as a plain name, never a directive, and the prefix it would have declared
# is never registered; when that is the one lv2:binary or rdfs:seeAlso depends on, the pin silently drops the file
bombundle=$work/lv2/bom-fixture.lv2
mkdir -p "$bombundle"
: > "$bombundle/Noisy.so"
: > "$bombundle/Noisy.ttl"
printf '\357\273\277@prefix lv2: <http://lv2plug.in/ns/lv2core#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n<urn:plugin-hostd:test:noisy> a lv2:Plugin ; lv2:binary <Noisy.so> ; rdfs:seeAlso <Noisy.ttl> .\n' > "$bombundle/manifest.ttl"
out=$("$daemon" -c "$work/conf" --pin-files urn:plugin-hostd:test:noisy); rc=$?
want="root $bombundle
file manifest.ttl
file Noisy.so
file Noisy.ttl"
[ $rc -eq 0 ] && [ "$out" = "$want" ]; check $? "a manifest with a leading UTF-8 BOM: its first @prefix still resolves, so its binary and files are still pinned (rc $rc)"
[ "$out" = "$want" ] || echo "$out" | sed 's/^/     /'

# a file named by a percent-encoded IRI (Surge XT's libSurge%20XT.so): listed as the manifest writes it, the word of a pin
ebundle=$work/lv2/Surge-fixture.lv2
mkdir -p "$ebundle"
: > "$ebundle/libSurge XT.so"
cat > "$ebundle/manifest.ttl" <<'TTL'
@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
<urn:plugin-hostd:test:encoded> a lv2:Plugin ; lv2:binary <libSurge%20XT.so> .
<urn:plugin-hostd:test:stray> a lv2:Plugin ; lv2:binary <libSurge%ZZXT.so> .
TTL
out=$("$daemon" -c "$work/conf" --pin-files urn:plugin-hostd:test:encoded); rc=$?
[ $rc -eq 0 ] && [ "$out" = "root $ebundle
file manifest.ttl
file libSurge%20XT.so" ]; check $? "a percent-encoded name is listed as the manifest writes it (rc $rc)"
[ "$rc" -eq 0 ] || echo "$out" | sed 's/^/     /'
"$daemon" -c "$work/conf" --pin-files urn:plugin-hostd:test:stray >/dev/null 2>"$work/err"; rc=$?
[ $rc -eq 1 ] && grep -q 'is not a percent-encoded name' "$work/err"; check $? "a stray percent in a name exits 1 with its reason ($rc: $(cat "$work/err"))"

# a bundle directory with a space, its binary named by the bundle's own file:// IRI, which writes the space %20: the
# IRI is decoded once before it is matched against the bundle, and the binary is a name in it
sbundle="$work/lv2/my amp.lv2"
mkdir -p "$sbundle"
: > "$sbundle/amp.so"
cat > "$sbundle/manifest.ttl" <<TTL
@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
<urn:plugin-hostd:test:spaced-bundle> a lv2:Plugin ; lv2:binary <file://$(printf %s "$sbundle" | sed 's/ /%20/g')/amp.so> .
TTL
out=$("$daemon" -c "$work/conf" --pin-files urn:plugin-hostd:test:spaced-bundle 2>"$work/err"); rc=$?
[ $rc -eq 0 ] && [ "$out" = "root $sbundle
file manifest.ttl
file amp.so" ]; check $? "a bundle directory with a space: its own file:// IRI names a file of the bundle (rc $rc: $(cat "$work/err"))"
[ "$rc" -eq 0 ] || echo "$out" | sed 's/^/     /'

out=$("$daemon" -c "$work/conf" --pin-files "clap:/usr/lib/clap/some plugin.clap#org.example.x"); rc=$?
[ $rc -eq 0 ] && [ "$out" = "root /usr/lib/clap
file some%20plugin.clap" ]; check $? "a CLAP plugin: its .clap file beside its directory, one percent-encoded word"
# a CLAP directory bundle (Cardinal, Ildaeil): the pin holds the one object inside it, not the directory
mkdir -p "$work/clapdir/Bundled.clap"
: > "$work/clapdir/Bundled.clap/Bundled.clap"
out=$("$daemon" -c "$work/conf" --pin-files "clap:$work/clapdir/Bundled.clap#org.example.x"); rc=$?
[ $rc -eq 0 ] && [ "$out" = "root $work/clapdir
file Bundled.clap/Bundled.clap" ]; check $? "a CLAP directory bundle: its one object inside it (rc $rc)"
[ "$rc" -eq 0 ] || echo "$out" | sed 's/^/     /'
: > "$work/clapdir/Bundled.clap/Second.clap"
"$daemon" -c "$work/conf" --pin-files "clap:$work/clapdir/Bundled.clap#org.example.x" >/dev/null 2>"$work/err"; rc=$?
[ $rc -ne 0 ] && grep -q 'without exactly one' "$work/err"; check $? "a directory bundle with two .clap files is refused with its reason ($rc: $(cat "$work/err"))"
exit $failed
