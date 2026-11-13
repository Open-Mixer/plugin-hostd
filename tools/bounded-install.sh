#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# bounded-install.sh <command> [<arg> ...]: a package manager's command in CI, bounded. Each attempt runs at most
# BOUNDED_INSTALL_TIMEOUT_S seconds (default 180); an attempt that times out is tried again, BOUNDED_INSTALL_RETRIES
# more times (default 2), so a mirror that hangs costs at most three attempts, under ten minutes, never the job's
# timeout-minutes. An attempt that fails otherwise (an unmet dependency, a package that is not there) is red at once:
# trying it again would answer the same. A red is one ::error:: line naming the command and the mirrors the package
# manager reads (the apt sources and the dnf repositories, or BOUNDED_INSTALL_SOURCES, files to read instead).
attempt_s=${BOUNDED_INSTALL_TIMEOUT_S:-180}
tries=$((${BOUNDED_INSTALL_RETRIES:-2} + 1))

mirrors() {
    files=${BOUNDED_INSTALL_SOURCES:-$(ls /etc/apt/sources.list /etc/apt/sources.list.d/* /etc/yum.repos.d/*.repo 2>/dev/null)}
    # shellcheck disable=SC2086
    sed -n 's/^deb\(-src\)\{0,1\} \(\[[^]]*\] \)\{0,1\}\([^ ]*\).*/\3/p; s/^URIs: *//p; s/^\(baseurl\|metalink\|mirrorlist\) *= *//p' $files 2>/dev/null |
        sort -u | tr '\n' ' '
}

n=1
while :; do
    timeout -k 10 "$attempt_s" "$@"
    rc=$?
    [ "$rc" = 0 ] && exit 0
    # timeout answers 124 when it ends the command, 137 when the command needed its KILL
    if [ "$rc" != 124 ] && [ "$rc" != 137 ]; then
        echo "::error::bounded-install: $* exited $rc (not a timeout, not tried again); the mirrors it reads: $(mirrors)" >&2
        exit 1
    fi
    echo "bounded-install: attempt $n of $tries: $* timed out after ${attempt_s} s" >&2
    [ "$n" -ge "$tries" ] && break
    n=$((n + 1))
done
echo "::error::bounded-install: $* timed out $tries attempts of ${attempt_s} s; the mirrors it reads: $(mirrors)" >&2
exit 1
