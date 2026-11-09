<!-- SPDX-License-Identifier: GPL-3.0-or-later
     Copyright (C) 2026 Pau Aliagas -->

Threat model
============

What it is and where it runs
----------------------------

plugin-hostd is a supervisor. It speaks mod-host's line protocol on a TCP command port (default 5555) and a feedback
port (the command port plus one), and runs every plugin in a worker process it starts: `omx-clap-host` for CLAP and,
by default, LV2, or `mod-host` when `lv2_worker mod-host` is set. The daemon itself never `dlopen`s plugin code; audio
and MIDI never pass through it, every worker is a JACK client (`README.md`, `doc/plugin-hostd.1`).

- Sockets: IPv4 TCP, both ports bound to `bind_address`, default `127.0.0.1` (`src/main.c`, `src/relay.c`,
  `src/conf.c`). One controller is served at a time. Workers listen on ephemeral ports on `127.0.0.1` (`proc_spawn` in
  `src/proc.c`).
- User: whatever user starts it. This tree ships no systemd unit and creates no service user (`packaging/`,
  `debian/`); a run as root is possible and changes the default directories to `/var/lib/omx/...`.
- Threads: the command loop, the relay thread (`src/relay.c`) and the writer thread (`src/writer.c`). The daemon sets
  no real-time priority; it only sets CPU affinity (`src/supervisor.c`, `src/proc.c`). A worker's audio thread gets
  its priority from the JACK client library.
- Isolation: one process per plugin, per pool or per chain, so a crash takes down its worker only. Workers run as
  the daemon's user with its environment, with `PR_SET_PDEATHSIG`; there is no namespace, seccomp, cgroup or rlimit
  around a worker. The descriptor scan (`plugin-hostd-probe describe|panel`) also runs in a child of its own
  (`src/descriptors.c`). Only `plugin-hostd-probe run` bounds its measured child (rlimits, memory cgroup, no new
  privileges, capabilities dropped; `src/probe.c`, `src/probe_cgroup.c`, `docs/guide.md`).

Inputs
------

| Input | Who can write it | Trusted? |
| --- | --- | --- |
| Commands on the command port (`add`, `pin_set`, `pin_accept`, `pin_clear`, `worker_env`, `preset_load/save`, ...) | any process that can reach the port: local users by default, any host once `bind_address` is widened | untrusted, not authenticated |
| Worker feedback lines (relayed to the controller) | the worker, which runs plugin code | untrusted |
| Plugin binaries (`.clap`, LV2 `.so`) | plugin author, packager, any user who can write the path named in `add` | untrusted code; run in a worker, never in the daemon |
| LV2 `manifest.ttl` and the files it names | plugin author / packager | untrusted; read by the daemon to collect pinned files |
| Descriptor and panel JSON from `plugin-hostd-probe` stdout | produced by scanning the plugin | partly plugin-derived; parsed by the daemon with cJSON |
| Preset files (`org.openmixer.preset`) named by `preset_load` / `preset_show` | whoever can write the path the controller names | untrusted; passed to the worker |
| Settings file (`-c`, `$PLUGIN_HOSTD_CONF`, `~/.config/plugin-hostd.conf`) | local user | trusted: `mod_host`, `clap_host` and `probe` name programs the daemon executes |
| Pin store, `<pin_store>.accepted`, `pin_file`, history file | local user (and the daemon) | trusted |
| `pins_dir` (`/usr/share/plugin-hostd/pins.d/*.pins`) | packager | trusted as it is |
| Qualification records (`qualification_dir`) | plugin-qualify, local user | trusted; read with a 4 MiB cap |
| Environment: `PATH`, `HOME`, `XDG_*`, `LV2_PATH`, `CLAP_PATH`, `OMX_DESCRIPTOR_DIR`, `OMX_QUALIFICATION_DIR`, `DISPLAY`/`WAYLAND_DISPLAY` | local user | trusted; inherited by every worker |
| Audio and MIDI | any JACK client | never read by the daemon; reach the plugin inside its worker |

A loaded plugin is arbitrary code running as the daemon's user inside its worker. The code assumes nothing about it
beyond what a pin says: with `require_pins 1` (the default) the bytes it loads are the bytes that were hashed, and
with a `verdict=in-process` pin it may share a worker. A pin records which files were checked; it does not make a
plugin safe, and under `pin_mode first-use` (the default) the first `add` of a plugin inside the declared search path
records its pin without any qualification.

Trust boundary
--------------

The boundary is the command port. Whoever can connect to it can load a plugin from any path, set, accept and clear
pins (`pin_set`, `pin_accept`, `pin_clear`), and so run code as the daemon's user; there is no authentication, so the
default loopback bind is the only access control. Plugins, their bundles and what workers write back are on the far
side of the boundary. The settings file, the pin store and the environment are on the near side: they belong to the
user the daemon runs as.

What the code assumes and enforces
----------------------------------

- Command lines: at most `line_max`, 4096 bytes, the protocol socket's buffer (`SOCKET_MSG_BUFFER_SIZE` in
  `src/main.c`); words bounded by `PHD_LINE_WORDS_MAX` (`src/verbs.c`). A verb parsed by the daemon is checked against
  its declared arity; anything else is refused with `-902` or passed to the worker to refuse. Tagged (`@`) lines never
  reach a worker. The reply queue is capped (`OUTBOX_MAX` 256, `src/verbs.c`).
- Sessions: extensions granted by `hello` and monitors are reset when a controller disconnects (`session_reset` in
  `src/session.c`, `src/main.c`).
- Worker feedback: a line longer than 1 MiB (`LINE_LIMIT`, `src/relay.c`) is dropped and its buffer stays bounded.
- Pins (`src/pins.c`): `pins_check` runs before any worker sees an `add`. Every file the format names must be held by
  the pin, and each pinned file is opened once, checked to be a regular file, and SHA-256 hashed on that descriptor
  (`hash_file`). Missing pin: `-508`; changed, missing or unheld file: `-509`; `verdict=refused`: `-516` unless the
  user's `pin_accept`. Pin paths are relative, without `..` or empty components, and percent-escaped (`path_valid`,
  `full_path`). A `pin_set` line that does not fit `line_max` is refused.
- First use (`record` in `src/pins.c`): a pin is learned only for files that resolve, symbolic links and `..`
  followed, inside a directory of the format's declared search path (`clap_path`, or `lv2_path` with `lv2_extra`);
  anything else stays unpinned and its `add` answers `-508` before any worker sees it. Whoever can write into a declared
  directory still gets a first-use pin for what they put there.
- LV2 manifests (`src/lv2.c`): read only when a regular file of at most 4 MiB (`MANIFEST_MAX`); a name that climbs out
  of the bundle or is absolute is never matched by a pin; a manifest using `@base` is refused with `-509`.
- Pinned LV2 plugins get a worker of their own whose LV2 world is narrowed to the plugin's bundle (`src/lv2.c`,
  `src/supervisor.c`); this limits what the worker loads, not what the plugin can do.
- Settings: values longer than their field are refused; `bind_address` must parse as IPv4 (`src/conf.c`). `descriptor_dir` and
  `qualification_dir` are created mode 0700 and an unwritable one stops the daemon (`-528`). Descriptor temp files are created
  `O_EXCL` mode 0600 (`src/descriptors.c`); the history file is mode 0600.
- Windows: `show_external_ui` is refused with `-902` when the daemon has neither `WAYLAND_DISPLAY` nor `DISPLAY`.

Not enforced:

- The pin is checked by the daemon and the file is then opened again, by path, by the worker; a file swapped between
  the two is not caught by the daemon.
- `state_root` defaults to `$XDG_RUNTIME_DIR`, else `/tmp`. The daemon `mkdir`s `plugin-hostd/<pid>` there mode 0755
  without checking the result or the owner, and writes worker and scan logs with `O_TRUNC` and no `O_NOFOLLOW`
  (`proc_spawn` in `src/proc.c`, `src/supervisor.c`, `src/descriptors.c`).
- The probe's stdout is read into memory without a size cap before parsing (`src/descriptors.c`).
- Worker ports on `127.0.0.1` accept any local process; only the daemon is meant to connect.
- With `require_pins 0` no file is checked at all.

Fuzz coverage
-------------

The harnesses are described in `fuzz/README.md` and run in CI on every push and pull request
(`.github/workflows/fuzz.yml`), under ASan and UBSan.

| Untrusted input | Harness |
| --- | --- |
| Commands on the command port | `fuzz/fuzz_command.c`: `verbs_receive` and the dispatcher in `src/verbs.c`, the pin line grammar in `src/pin_words.c` |
| Worker feedback lines | `fuzz/fuzz_reply.c`: the feedback reader of `src/relay.c` |

`fuzz_command` replaces everything below the dispatcher with `fuzz/recorder.c`, so the supervisor, the pin checks and
the format code are not driven by it.

Gaps (no fuzz target):

- LV2 Turtle reading in `src/lv2.c` (the hand-written scanner behind the pin's file list and the world narrowing).
- Pin file and pin store parsing beyond the `pin_set` grammar (`file_read`, `line_read` in `src/pins.c`).
- Descriptor and panel JSON from the probe (`src/descriptors.c`, `src/describe.c`) and qualification records
  (`src/qualcost.c`); these are parsed by cJSON, itself not fuzzed here.
- Preset files: no reader for them was found under `src/`; the path is passed to the worker, and their checks live
  there.
- CLAP descriptors are read by the worker and the scanner, not by the daemon; this tree does not fuzz them.
- The settings file (`src/conf.c`) and the history file (`src/history.c`).

Reporting
---------

Report a vulnerability privately through GitHub: the repository's Security tab, "Report a vulnerability".
The policy is the organisation's `SECURITY.md`.
