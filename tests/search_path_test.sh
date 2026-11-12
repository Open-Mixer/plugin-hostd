#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# plugin-hostd --search-path: the LV2 and CLAP directories the daemon searches with its settings, and where each list
# comes from, so plugin-qualify scans exactly them (plugin-qualify#9). The file is over the environment, which is over
# the default; lv2_extra follows lv2_path in the effective LV2 list; CLAP_PATH comes before the default CLAP list; "~"
# is expanded under $HOME; a -c file that cannot be read is an error.
set -u
daemon=${1:-./plugin-hostd}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failed=0
check() { if [ "$1" = 0 ]; then echo "ok   $2"; else echo "FAIL $2"; failed=1; fi; }
# the value of <key> for <source> in the output, or a line no output holds
field() { printf '%s\n' "$1" | awk -F '\t' -v k="$2" -v s="$3" '$1 == k && $2 == s { print $3; found = 1 } END { if (!found) print "<no " k " from " s ">" }'; }
run() { env -u LV2_PATH -u CLAP_PATH HOME="$work/home" "$@" "$daemon" -c "$work/conf" --search-path 2>"$work/err"; }

: > "$work/conf"
out=$(run); rc=$?
check $rc "an empty settings file answers ($rc: $(cat "$work/err"))"
default_lv2=$(field "$out" lv2_path default)
check $([ -n "$default_lv2" ] && [ "$default_lv2" = "$(field "$out" lv2 effective)" ] && echo 0 || echo 1) \
  "with no file key and no environment, lv2_path is the default and is what is searched: $out"
clap=$(field "$out" clap effective)
case "$clap" in "$work/home/"*) r=0 ;; *) r=1 ;; esac
check $r "the default CLAP list has ~ expanded under \$HOME: $clap"
check $([ "$(field "$out" clap_path default)" = "$clap" ] && echo 0 || echo 1) "the CLAP list is the default one, named default"

out=$(run LV2_PATH=/env/lv2 CLAP_PATH=/env/clap); rc=$?
check $([ "$rc" = 0 ] && [ "$(field "$out" lv2_path env)" = /env/lv2 ] && [ "$(field "$out" lv2 effective)" = /env/lv2 ] && echo 0 || echo 1) \
  "LV2_PATH is over the default and named env: $out"
check $([ "$(field "$out" clap_path env)" = "/env/clap:$clap" ] && echo 0 || echo 1) \
  "CLAP_PATH comes before the default CLAP list, named env: $(field "$out" clap_path env)"

printf 'lv2_path /file/lv2:~/lv2\nlv2_extra /file/extra\nclap_path /file/clap\n' > "$work/conf"
out=$(run LV2_PATH=/env/lv2 CLAP_PATH=/env/clap); rc=$?
check $([ "$(field "$out" lv2_path file)" = "/file/lv2:$work/home/lv2" ] && echo 0 || echo 1) \
  "the file is over LV2_PATH, named file, ~ expanded: $(field "$out" lv2_path file)"
check $([ "$(field "$out" lv2_extra file)" = /file/extra ] && echo 0 || echo 1) "lv2_extra from the file is named file"
check $([ "$(field "$out" lv2 effective)" = "/file/lv2:$work/home/lv2:/file/extra" ] && echo 0 || echo 1) \
  "the LV2 list searched is lv2_path then lv2_extra: $(field "$out" lv2 effective)"
check $([ "$(field "$out" clap_path file)" = /file/clap ] && [ "$(field "$out" clap effective)" = /file/clap ] && echo 0 || echo 1) \
  "the file is over CLAP_PATH: $(field "$out" clap effective)"

env -u LV2_PATH -u CLAP_PATH "$daemon" -c "$work/none.conf" --search-path >/dev/null 2>"$work/err"; rc=$?
check $([ "$rc" != 0 ] && grep -q "none.conf" "$work/err" && echo 0 || echo 1) "a -c file that cannot be read is an error ($rc: $(cat "$work/err"))"
exit $failed
