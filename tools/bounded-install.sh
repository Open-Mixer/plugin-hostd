#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# bounded-install.sh <command> [<arg> ...]: a package manager's command in CI, bounded by inactivity. An attempt ends
# when the command prints nothing and makes no progress for BOUNDED_INSTALL_IDLE_S seconds (default 120: a mirror that
# hangs) or runs past
# BOUNDED_INSTALL_TOTAL_S (default 900, generous: a slow install that keeps printing, still unpacking, is progress and is
# never ended for being slow). An attempt so ended is tried again, BOUNDED_INSTALL_RETRIES more times (default 2), after
# dpkg --configure -a for an apt command (an ended unpack leaves dpkg interrupted); an attempt that fails otherwise (an
# unmet dependency, a package that is not there) is red at once, since trying it again would answer the same. A red is
# one ::error:: line naming the command and the mirrors the package manager reads (the apt sources and the dnf
# repositories, or BOUNDED_INSTALL_SOURCES, files to read instead).
# Silence is not stillness: dpkg's configure phase prints nothing while it works. At the end of a silent window the
# attempt goes on when its process tree used CPU (a hundredth of the window at least) or dpkg's status moved
# (BOUNDED_INSTALL_DPKG_DIR, default /var/lib/dpkg: status, updates/, lock); only a silent and still one is ended.
idle_s=${BOUNDED_INSTALL_IDLE_S:-120}
total_s=${BOUNDED_INSTALL_TOTAL_S:-900}
tries=$((${BOUNDED_INSTALL_RETRIES:-2} + 1))

mirrors() {
    local files=${BOUNDED_INSTALL_SOURCES:-$(ls /etc/apt/sources.list /etc/apt/sources.list.d/* /etc/yum.repos.d/*.repo 2>/dev/null)}
    # shellcheck disable=SC2086
    sed -n 's/^deb\(-src\)\{0,1\} \(\[[^]]*\] \)\{0,1\}\([^ ]*\).*/\3/p; s/^URIs: *//p; s/^\(baseurl\|metalink\|mirrorlist\) *= *//p' $files 2>/dev/null |
        sort -u | tr '\n' ' '
}

# the CPU ticks, in clock ticks, of a process and of every descendant, the children it reaped included (apt runs dpkg
# in a session of its own, and dpkg runs short-lived maintainer scripts; descent is by parent, not by group)
tree_ticks() {
    local f line pid rest total=0 todo seen
    local -A kids=() cpu=()
    for f in /proc/[0-9]*/stat; do
        { IFS= read -r line <"$f"; } 2>/dev/null || continue  # a process may end between the glob and the read
        pid=${line%% *}
        rest=${line##*) }
        # shellcheck disable=SC2086
        set -- $rest
        kids[$2]+=" $pid"
        cpu[$pid]=$((${12} + ${13} + ${14} + ${15}))
    done
    todo=$root_pid
    seen=" "
    while [ -n "$todo" ]; do
        set -- $todo
        pid=$1
        shift
        todo="$* ${kids[$pid]:-}"
        todo=${todo# }
        case $seen in *" $pid "*) continue ;; esac
        seen="$seen$pid "
        total=$((total + ${cpu[$pid]:-0}))
    done
    echo "$total"
}
dpkg_dir=${BOUNDED_INSTALL_DPKG_DIR:-/var/lib/dpkg}
hz=$(getconf CLK_TCK)
dpkg_mark() { stat -c %Y.%Z "$dpkg_dir/status" "$dpkg_dir/updates" "$dpkg_dir/lock" 2>/dev/null | tr '\n' ' '; }
# 0 when the attempt moved since the last call: its tree's CPU by a hundredth of the window, or dpkg's status files;
# says which in $moved
progressed() {
    local ticks mark
    ticks=$(tree_ticks)
    mark=$(dpkg_mark)
    moved=
    if ((ticks - last_ticks >= idle_s * hz / 100)); then
        moved="its processes used $(((ticks - last_ticks) * 100 / hz)) cs of CPU"
    elif [ "$mark" != "$last_mark" ]; then moved="dpkg's status moved"; fi
    last_ticks=$ticks
    last_mark=$mark
    [ -n "$moved" ]
}

# one attempt: the command's output passed on line by line; ended (its whole process group) when no line comes for
# idle_s and the attempt made no progress in that window, or the attempt passes total_s. Sets $ended to idle, total or
# nothing, and returns the command's status.
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
    root_pid=$pid
    last_ticks=$(tree_ticks)
    last_mark=$(dpkg_mark)
    exec 3<"$fifo"
    rm -f "$fifo"
    while :; do
        if IFS= read -r -t "$idle_s" line <&3; then
            printf '%s\n' "$line"
            if ((SECONDS - started >= total_s)); then ended=total; break; fi
        elif (($? > 128)); then
            if ((SECONDS - started >= total_s)); then ended=total; break; fi
            if progressed; then
                echo "bounded-install: $1 printed nothing for ${idle_s} s, but $moved: waiting on" >&2
                continue
            fi
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

# apt runs dpkg in a session of its own, which ending the attempt's process group does not reach: the processes that hold
# dpkg's lock (BOUNDED_INSTALL_DPKG_LOCK) are given the idle bound to finish, then ended. They are found by the lock
# file among their open files, so a dpkg that holds no lock, or one of another lock file, is never touched
lock_holders() {
    local fd
    for fd in /proc/[0-9]*/fd/*; do
        [ "$(readlink "$fd" 2>/dev/null)" = "$dpkg_lock" ] && { fd=${fd#/proc/}; echo "${fd%%/*}"; }
    done | sort -u
}
free_dpkg_lock() {
    local holders waited=0
    holders=$(lock_holders)
    while [ -n "$holders" ] && [ "$waited" -lt "$idle_s" ]; do
        sleep 1
        waited=$((waited + 1))
        holders=$(lock_holders)
    done
    [ -n "$holders" ] || return 0
    echo "bounded-install: ending what still holds $dpkg_lock after ${idle_s} s: $(echo $holders)" >&2
    kill -TERM $holders 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do [ -z "$(lock_holders)" ] && return 0; sleep 0.5; done
    kill -KILL $(lock_holders) 2>/dev/null
    sleep 0.5
}
dpkg_lock=${BOUNDED_INSTALL_DPKG_LOCK:-/var/lib/dpkg/lock}

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
    # dpkg's work first, from what was already fetched, once no dpkg of the ended attempt still holds the lock
    case $1 in apt | apt-get) free_dpkg_lock; dpkg --configure -a ;; esac
    n=$((n + 1))
done
echo "::error::bounded-install: $* $why, $tries attempts; the mirrors it reads: $(mirrors)" >&2
exit 1
