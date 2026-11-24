# SPDX-License-Identifier: GPL-3.0-or-later
# Declared ahead of the daemon: the verbs plugin-hostd-protocol declares for plugin-hostd that the daemon still relays to
# its worker unanswered. AHEAD is empty now: property_get, property_info, property_list and property_set, once declared
# ahead, are answered by the daemon (plugin-hostd#124) and held to their declaration. tests/verbs_declared.py leaves only
# the verbs of AHEAD out of its "seen in the binary" and "answered by the daemon" checks, and only while they stay
# unanswered: any other declared verb the daemon relays is red, a verb of AHEAD the declarations no longer give
# plugin-hostd is red, and one the daemon answers itself is red, so the allowance goes and its answer is held to its
# declaration.
# Usage: verbs_ahead.py --self-test
import sys

AHEAD = set()


def ahead_of_daemon(ours, unseen, relayed, answered, AHEAD=AHEAD):
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
    AHEAD = {"property_get", "property_info", "property_list", "property_set"}  # the allowance's own example
    ours = AHEAD | {"add", "remove"}
    # the four, relayed and not in the binary, pass
    u, r, p = ahead_of_daemon(ours, set(AHEAD), set(AHEAD), {"add", "remove"}, AHEAD)
    assert (u, r, p) == (set(), set(), []), (u, r, p)
    # a fifth declared verb the daemon relays stays red, as does one the binary does not hold
    u, r, p = ahead_of_daemon(ours | {"fake_verb"}, AHEAD | {"fake_verb"}, AHEAD | {"fake_verb"}, {"add", "remove"}, AHEAD)
    assert u == {"fake_verb"} and r == {"fake_verb"} and not p, (u, r, p)
    # one of the four that the daemon answers itself is red
    u, r, p = ahead_of_daemon(ours, set(), AHEAD - {"property_set"}, {"add", "remove", "property_set"}, AHEAD)
    assert not u and not r and len(p) == 1 and "property_set" in p[0], (u, r, p)
    # one of the four that is no longer declared is red
    u, r, p = ahead_of_daemon(ours - {"property_list"}, set(), set(), {"add", "remove"}, AHEAD)
    assert len(p) == 1 and "property_list" in p[0], (u, r, p)
    # no allowance: nothing is left out
    u, r, p = ahead_of_daemon(ours, {"add"}, {"remove"}, {"add", "remove"} | AHEAD)
    assert (u, r, p) == ({"add"}, {"remove"}, []), (u, r, p)
    print("ok   verbs_ahead --self-test: only the verbs given as declared ahead pass, and only while unanswered")


if __name__ == "__main__":
    if sys.argv[1:] != ["--self-test"]:
        sys.exit("usage: verbs_ahead.py --self-test")
    self_test()
