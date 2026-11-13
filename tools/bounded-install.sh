#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# bounded-install.sh <command> [<arg> ...]: a package manager's command in CI, bounded by inactivity. An attempt ends
# when the command prints nothing for BOUNDED_INSTALL_IDLE_S seconds (default 120: a mirror that hangs) or runs past
# BOUNDED_INSTALL_TOTAL_S (default 900, generous: a slow install that keeps printing, still unpacking, is progress and is
# never ended for being slow). An attempt so ended is tried again, BOUNDED_INSTALL_RETRIES more times (default 2), after
# dpkg --configure -a for an apt command (an ended unpack leaves dpkg interrupted); an attempt that fails otherwise (an
# unmet dependency, a package that is not there) is red at once, since trying it again would answer the same. A red is
# one ::error:: line naming the command and the mirrors the package manager reads (the apt sources and the dnf
# repositories, or BOUNDED_INSTALL_SOURCES, files to read instead).
idle_s=${BOUNDED_INSTALL_IDLE_S:-120}
total_s=${BOUNDED_INSTALL_TOTAL_S:-900}
tries=$((${BOUNDED_INSTALL_RETRIES:-2} + 1))

mirrors() {
    local files=${BOUNDED_INSTALL_SOURCES:-$(ls /etc/apt/sources.list /etc/apt/sources.list.d/* /etc/yum.repos.d/*.repo 2>/dev/null)}
    # shellcheck disable=SC2086
    sed -n 's/^deb\(-src\)\{0,1\} \(\[[^]]*\] \)\{0,1\}\([^ ]*\).*/\3/p; s/^URIs: *//p; s/^\(baseurl\|metalink\|mirrorlist\) *= *//p' $files 2>/dev/null |
        sort -u | tr '\n' ' '
}

# one attempt: the command's output passed on line by line; ended (its whole process group) when no line comes for
# idle_s or the attempt passes total_s. Sets $ended to idle, total or nothing, and returns the command's status.
attempt() {
    local fifo line started=$SECONDS pid status
    ended=
    fifo=$(mktemp -u)
    mkfifo "$fifo"
    # a process group of its own, so an ended attempt takes its children (dpkg under apt) with it; without setsid, the
    # command itself
    local group=-
    if command -v setsid >/dev/null; then setsid "$@" >"$fifo" 2>&1 & else group= ; "$@" >"$fifo" 2>&1 & fi
    pid=$!
    exec 3<"$fifo"
    rm -f "$fifo"
    while :; do
        if IFS= read -r -t "$idle_s" line <&3; then
            printf '%s\n' "$line"
            if ((SECONDS - started >= total_s)); then ended=total; break; fi
        elif (($? > 128)); then
            ended=idle
            break
        else
            [ -n "$line" ] && printf '%s\n' "$line"
            break
        fi
    done
    if [ -n "$ended" ]; then
        kill -TERM -- "$group$pid" 2>/dev/null
        # up to 5 s to end on TERM, then KILL
        for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
        kill -KILL -- "$group$pid" 2>/dev/null
    fi
    exec 3<&-
    wait "$pid"
    status=$?
    return "$status"
}

n=1
while :; do
    attempt "$@"
    rc=$?
    [ -z "$ended" ] && [ "$rc" = 0 ] && exit 0
    if [ -z "$ended" ]; then
        echo "::error::bounded-install: $* exited $rc (not a stall, not tried again); the mirrors it reads: $(mirrors)" >&2
        exit 1
    fi
    if [ "$ended" = idle ]; then why="printed nothing for ${idle_s} s"; else why="ran past ${total_s} s"; fi
    echo "bounded-install: attempt $n of $tries: $* $why" >&2
    [ "$n" -ge "$tries" ] && break
    # an apt attempt ended mid-unpack leaves dpkg interrupted, which the next attempt would refuse at once: finish
    # dpkg's work first, from what was already fetched
    case $1 in apt | apt-get) dpkg --configure -a ;; esac
    n=$((n + 1))
done
echo "::error::bounded-install: $* $why, $tries attempts; the mirrors it reads: $(mirrors)" >&2
exit 1
