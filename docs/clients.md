The protocol clients
====================

plugin-hostd ships the clients of its protocol, one per language a controller is written in: Python
(`clients/python`, the package `plugin_hostd_protocol`, shipped as python3-plugin-hostd-protocol) and
TypeScript (`clients/ts`, the npm package `@openmixer/plugin-hostd-client`). A controller speaks the
protocol through one of them and restates nothing: openmixer's server drops its own speaker for the
TypeScript client, Zynthian's fork drops its own for the Python one
(Open-Mixer/zynthian-ui#4). Ruled in #29 (owner, 2026-11-01, thin integration and one project; widened
2026-11-12 to both languages).

What a client knows
-------------------

Nothing of the protocol is written in a client. Each reads, when it is loaded, the files
plugin-hostd-protocol installs:

| What | Where it is installed | Read for |
|---|---|---|
| the protocol table | `pkg-config --variable=table plugin-hostd-protocol` (`plugin-hostd-protocol.json`) | every command, its forms and the type of each argument; the feedback lines; the protocol errors; every reply code by number |
| the vocabulary | omx-contract's contract directory, `3/plugin-hostd-protocol/verbs.json` and `3/omx-clap-core/verbs.json` | a reply code's English sentence |
| the catalogs | `catalogs/<lang>.json` beside the table | a reply code's sentence in another language |

A client is given these paths, or finds them where the package installs them; a file that is not there is
an error that names it, never an empty protocol.

What a client does
------------------

Both clients are the same codec over that table, with the same names (snake_case in Python, camelCase in
TypeScript):

- **encode**(verb, args[, tag]): the line of a command the table declares, after `@<tag>` when a request tag is
  given (the tags extension). The form is the first whose arguments
  fit; an `int` is an integer, a `float` a finite number written in its shortest form that reads back to
  the same double (an integral one without a fraction, an exponent without leading zeros), a `word` one
  word of the grammar (bare when it can be, else in quotation marks with `\"` for a quote), a `tail` the
  rest of the line. A verb the table does not declare, or arguments no form takes, is an error, never a
  line.
- **decode**(line): a command line back into its verb, its arguments and its request tag, by the same table;
  **reencode**(line), the same line decoded and encoded again.
- **parse**(line): what the host or the daemon answered, a request tag (`@<tag>`) and a sequence number
  first when the line carries them: `resp <code> [data]` with the code's name, a
  feedback line by its declared arguments, or a protocol error. A line of plugin-hostd's own carries its
  `fields` too, each argument by the name its declared form gives it (plugin-hostd-protocol 0.5.6): the
  form with the most arguments the words fit is read first, so `instance_verb_dropped`'s suspect form wins
  over the one whose command takes the rest of the line.
- **read_reply**(verb, data[, code]) (`readReply`): the data words of a reply, after `resp <code>`, by
  the table's `reply_forms` (plugin-hostd-protocol 0.5.7): each word by its name, as its declared type. A
  leaf is read by its pattern (an `int`, `uint`, `core` or `amount` a number, `-` none for a core or an
  amount, a `number` a finite number); a list is a list, one of its none words an empty one; a record is
  its fields by name, found by the record's own pattern, so a field may hold the separator (a worker's
  `place`, `pool:fx#2`, inside a `worker_list` record). A reply whose number counts (`worker_list`) is held
  to that count when it is given. The clients keep no layout of their own: every shape is the table's.
- **read_plan**(data), **read_plan_get**(data), **read_estimate**(data) (`readPlan`, `readPlanGet`,
  `readEstimate` in TypeScript): the data words of three replies, read by **read_reply**, with what the
  table does not say: the cores in the segments' shape, a reason's word, code and retry, a code's name. A plan is its `segments` (the instances that share a worker, in signal order) and
  its `cores` in the same shape, none for a member that is not pinned. A plan read back also gives its
  `reasons`: the instance, the reason as written, its word of `PLUGIN_HOSTD_GROUPING_REASONS`, the reply
  code a `plan-refused` carries with its name, and `retry`, true for the reasons a later plan may not give
  again with the chain unchanged (`RETRY_REASONS`: the reasons whose group `data/grouping.json` declares `retry`, `no-verdict` and
  `plan-refused` today, written from the file by the same tool as `GroupingReason`). An estimate is every figure by the protocol's
  name (`latency_frames`, `cpu_percent`, `ram_bytes`, `workers`, `unknown_count`, `members` with the
  reply code of each one that has no figure, and the four memory figures), none for a figure the daemon
  answers `-`. A word that is not the shape is an error, never a guess.
- **GroupingReason**: the reasons a plan gives as constants, one for every word of
  `PLUGIN_HOSTD_GROUPING_REASONS` (`GroupingReason.GROUPING_OFF` in Python, `GroupingReason.groupingOff`
  in TypeScript, the key the file gives it), so a controller compares against them and writes no reason
  word. They are written from `data/grouping.json` by `tools/grouping-reasons.py` (`make
  render-grouping-reasons`), never by hand; `make check-grouping-reasons` fails on any drift, and the
  tests of both clients hold each declared reason to its constant and each constant to a declared reason
  (#67).
- the words of a line (`words`, `quote`), the percent-encoded path of a `clap:` uri (`encode_path`,
  `decode_path`, `uri_word`, `pin_key`), as the grammar and the pin section of plugin-hostd-protocol's
  documentation write them.
- **code**(name), **name**(code), **sentence**(code, lang): the reply codes, from the table and the
  vocabulary.

The clients carry no transport: a controller opens the socket and sends the lines.

How they are held to each other
-------------------------------

`clients/fixtures/codec.json` holds the requests and the replies both clients are tested on: each an
operation, its input and what it gives. `make test-clients` runs each client's own tests on them, then
`tests/clients_agree.py`, which hands both clients every fixture, every command line of
plugin-hostd-protocol's host scenarios (decoded and encoded again) and every reply those scenarios accept,
and is red for any input the two answer differently. Its self-test feeds it a client that answers one
input otherwise, and wants it red.
