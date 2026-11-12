The protocol clients
====================

plugin-hostd ships the clients of its protocol, one per language a controller is written in: Python
(`clients/python`, the package `plugin_hostd_protocol`, shipped as python3-plugin-hostd-protocol) and
TypeScript (`clients/ts`, the npm package `@openmixer/plugin-hostd-client`). A controller speaks the
protocol through one of them and restates nothing: openmixer's server drops its own speaker for the
TypeScript client (Open-Mixer/openmixer#120), Zynthian's fork drops its own for the Python one
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
  first when the line carries them: `resp <code> [data]` with the code's name and its sentence, a
  feedback line by its declared arguments, or a protocol error.
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
