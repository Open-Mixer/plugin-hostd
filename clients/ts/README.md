# @openmixer/plugin-hostd-client

The TypeScript client of plugin-hostd's protocol: one codec over the protocol table that
plugin-hostd-protocol installs. A controller speaks to plugin-hostd through it and restates
nothing of the protocol; the client carries no transport, so the controller opens the socket
and sends the lines.

## What it reads

Nothing of the protocol is written in the client. When a `Protocol` is made it reads the
files the packages install:

| What | Where | Read for |
|---|---|---|
| the protocol table | `PLUGIN_HOSTD_PROTOCOL_TABLE`, else `pkg-config --variable=table plugin-hostd-protocol` | every command, its forms, the type of each argument, the feedback lines, the protocol errors, every reply code by number |
| the vocabulary | `OMX_CONTRACT_PATH`, else `pkg-config --variable=contractdir omx-contract` | a reply code's English sentence |
| the catalogs | `pkg-config --variable=datadir plugin-hostd-protocol` | a reply code's sentence in another language |

A file that is not there is an error that names it, never an empty protocol. So the host
needs `plugin-hostd-protocol` (its `-devel` or `-dev` package carries the table and the
pkg-config file) and `omx-contract`, from the OpenMixer channel.

## Use

```ts
import { Protocol } from '@openmixer/plugin-hostd-client';

const protocol = new Protocol();            // the installed table and vocabulary
// or new Protocol({ table, contractDirs, datadir }) with explicit paths

protocol.encode('add', ['clap:...', 0]);     // the line to send, by the table's form
protocol.encode('add', ['clap:...', 0], 't1'); // the same line after a request tag

protocol.parse('resp 0');                     // what the host answered: a reply, feedback or a protocol error
protocol.decode('add clap:... 0');            // a command line back into verb, args and tag

protocol.name(-2);                            // a reply code's name
protocol.code('reply.host.instance-already-exists');
protocol.sentence(-2, 'ca');                  // its sentence in a listed language, English when the catalog lacks it
```

The grammar helpers are exported beside it: `words`, `quote`, `encodePath`, `decodePath`,
`uriWord`, `pinKey` and `formatNumber`, each as plugin-hostd-protocol's documentation writes it.

`plugin-hostd-codec` is the same codec as a command: a batch of cases on stdin,
`{"cases": [{"op", "in"}, ...]}`, each answered on stdout as `{"ok": value}` or
`{"error": message}`, in order. The protocol's test suite hands every fixture to this command
and to the Python client and is red when the two answer differently.

## Versions

The package carries plugin-hostd's version. A `-staged.N` version under the dist-tag `staged`
is a pre-release built from main for the staging channel; `latest` moves only at a release.

The source, the fixtures and the Python client live in
[Open-Mixer/plugin-hostd](https://github.com/Open-Mixer/plugin-hostd) under `clients/`;
`docs/clients.md` there says how the two clients are held to each other.

GPL-3.0-or-later.
