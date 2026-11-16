# SPDX-License-Identifier: GPL-3.0-or-later
# Declared ahead of the daemon: plugin-hostd-protocol 0.5.9 declares these four verbs for plugin-hostd, and this release
# relays them to its worker unanswered; the daemon answers them from 0.20.8 (plugin-hostd#124). tests/verbs_declared.py
# leaves only these four out of its "seen in the binary" and "answered by the daemon" checks, and only while they stay
# unanswered: any other declared verb the daemon relays is red, a verb of these four the declarations no longer give
# plugin-hostd is red, and one the daemon answers itself is red, so the allowance goes and its answer is held to its
# declaration.
# Usage: verbs_ahead.py --self-test
import sys

AHEAD = {"property_get", "property_info", "property_list", "property_set"}


def ahead_of_daemon(ours, unseen, relayed, answered):
    """(unseen, relayed, problems): the unseen and relayed declared verbs with AHEAD's left out, and the reds the
    allowance itself raises"""
    problems = []
    stale = sorted(AHEAD - ours)
    if stale:
        problems.append("allowed as declared ahead of the daemon, but not declared for plugin-hostd: %s" % stale)
    now = sorted(AHEAD & answered)
    if now:
        problems.append("the daemon answers %s itself: take them out of tests/verbs_ahead.py so their answer is checked"
                        % now)
    return unseen - AHEAD, relayed - AHEAD, problems


def self_test():
    ours = AHEAD | {"add", "remove"}
    # the four, relayed and not in the binary, pass
    u, r, p = ahead_of_daemon(ours, set(AHEAD), set(AHEAD), {"add", "remove"})
    assert (u, r, p) == (set(), set(), []), (u, r, p)
    # a fifth declared verb the daemon relays stays red, as does one the binary does not hold
    u, r, p = ahead_of_daemon(ours | {"fake_verb"}, AHEAD | {"fake_verb"}, AHEAD | {"fake_verb"}, {"add", "remove"})
    assert u == {"fake_verb"} and r == {"fake_verb"} and not p, (u, r, p)
    # one of the four that the daemon answers itself is red
    u, r, p = ahead_of_daemon(ours, set(), AHEAD - {"property_set"}, {"add", "remove", "property_set"})
    assert not u and not r and len(p) == 1 and "property_set" in p[0], (u, r, p)
    # one of the four that is no longer declared is red
    u, r, p = ahead_of_daemon(ours - {"property_list"}, set(), set(), {"add", "remove"})
    assert len(p) == 1 and "property_list" in p[0], (u, r, p)
    print("ok   verbs_ahead --self-test: only the four declared-ahead verbs pass, and only while unanswered")


if __name__ == "__main__":
    if sys.argv[1:] != ["--self-test"]:
        sys.exit("usage: verbs_ahead.py --self-test")
    self_test()
