The protocol clients
====================

The clients of plugin-hostd's protocol are plugin-hostd-protocol's: its Python codec (the package
`plugin_hostd_protocol`, python3-plugin-hostd-protocol) and its TypeScript codec. A controller speaks the protocol
through one of them and restates nothing (#29: thin integration, one project). This tree ships no client and keeps no
copy of one (`tests/no_protocol_copy.py`).

What this tree gives the clients is words: the reasons a plan gives for a plugin it leaves alone are the domain
`plugin-hostd/grouping` (`contract.d/plugin-hostd/grouping/grouping.json`, installed by `plugin-hostd-contract` to
`<contractdir>/plugin-hostd/grouping/`). plugin-hostd-protocol writes both clients' `GroupingReason` and
`RETRY_REASONS` from it; `make test-grouping-domain` here holds the installed Python client to the domain.

The tests of this tree drive the daemon through plugin-hostd-protocol's installed Python codec (`tests/daemon_test.py`)
and through plugin-hostd-protocol's installed Python client, `plugin_hostd_client` (`python3-plugin-hostd-client`,
plugin-hostd-protocol issue 45); `PLUGIN_HOSTD_CLIENT_DIR` names a plugin-hostd-protocol checkout's `clients/python`
instead. `plugin-hostd-tests` ships the shell client alone, `tests/lib/protocol.sh`.
