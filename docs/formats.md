The format tables: how a scan becomes a descriptor
===================================================

plugin-hostd turns what a CLAP or LV2 plugin states about itself into a `scanned` descriptor (omx-contract
`docs/descriptors.md`). Three layers do it, and each is one thing:

| Layer | What | Where |
|---|---|---|
| L1 description | one mapping table per format, data: every field a scan reads, mapped to a descriptor word, carried in the extension bag, or dropped by a named decision | the domain `plugin-hostd/clap` (`contract.d/plugin-hostd/clap/clap.json`, `PLUGIN_HOSTD_CLAP_MAP`) and the domain `plugin-hostd/lv2` (`PLUGIN_HOSTD_LV2_MAP`), each item an `x-kind` `map` (omx-contract's mapping-table kind), one row per source field |
| L2 transforms | a closed list of named functions, each with its inverse, which a table names and never defines | `src/transforms.h` (`TRANSFORMS(X)`), `src/transforms.c` |
| L3 runtime | the field dump of one plugin, read as a host reads it | omx-clap-core's `omx-clap-scan --fields` |

`plugin-hostd-probe describe` joins them: it runs the dump in an isolated child, applies the table and its transforms,
and writes the descriptor. The same tables, read backwards, are what omx-plugins' generators write a CLAP face and an
LV2 `.ttl` from: one vocabulary, two directions, and the round trip (author, generate both faces, scan back, compare)
is the proof.

## The tables

Each table is a domain of the contract directory (`docs/contract-dir.md` of omx-contract, Domains): `plugin-hostd/clap` and
`plugin-hostd/lv2`, named by their item's prefix, installed by `make install` (`install_vocabulary_domains`, with
omx-contract-devel's `install-contract-dir.sh --domain`) to `<contractdir>/plugin-hostd/<format>/<format>.json`, beside the
domains `plugin-hostd/grouping` and `plugin-hostd/history`. The daemon's verbs are the domain `plugin-hostd-protocol`
(`<contractdir>/plugin-hostd-protocol/plugin-hostd-protocol.json`), which plugin-hostd-protocol ships under its own name.
The document is a domain header (`$id`
`https://openmixer.org/contract/plugin-hostd/<format>`, `info.version`, `x-owner plugin-hostd`, `x-stability`) over one
item, `PLUGIN_HOSTD_<FORMAT>_MAP`, of `x-kind` `map` (omx-contract `docs/contract-dir.md`, Domains; the kind ruled for a
mapping table by the owner on 2026-11-23, decision 1 of plugin-hostd#215, omx-contract#191): its `description` is the
table's doc, its `x-format` the format, and its `oneOf` one row per source field, in the table's order: `const` and
`title` the source field, `x-code` its place, what it covers (`x-term` or `x-from`), its class (`x-word`, `x-extension`
or `x-dropped`) and its `description` the row's doc. That item is what `plugin-hostd-probe describe`,
`tests/format_coverage.py` and omx-plugins' generators (`tools/format-tables.mjs`) read, and what omx-contract's
`render --with-domain` rebuilds, byte for byte, as the data form's `formatMap` (`{ kind, format, rows }`, the row keys
`term`, `from`, `word`, `extension`, `dropped`, `doc`); this page names a row's parts by those data-form keys. The one `MANIFEST.json` of `<contractdir>/plugin-hostd/`
(`make install-contract`) names no file and the top-level domains this tree owns; it is what tells omx-contract's reader that
`<contractdir>/plugin-hostd/` holds domains. No copy of the tables stays under `plugin-hostd/formats/`. The noarch package plugin-hostd-contract
(`plugin-hostd-contract` on Debian too) ships them, and a program that reads them at run time requires it.
It requires omx-contract 3.2.0 or later (`Requires`, Debian `Depends`): the tables live in omx-contract's contract
directory and are read against its schema, and 3.2.0 is the first whose source field takes an index
(`omx_clap_panel_display.meter_ids[0]`), so an older omx-contract never sits beside a table it refuses.

`make check-contract-dir` installs the package and the domains into a staging directory and runs `omx-contract validate` over it
together with the installed contract directory (omx-contract's own tables, omx-clap-core's): red on any table the
installed schema refuses, and red, never a skip, when the `omx-contract` command is absent. The coverage test below
walks the schema for the words only, never for the row keys; this gate reads every key as a reader of the installed
directory does.

A table's `rows` are keyed by the source field, and each row has exactly one class:

| Class | Carries | Meaning |
|---|---|---|
| `word` | `{ word, transform, values? \| factor? }` | the descriptor word it becomes (`controls[].travel.unit`), the transform that converts it (a name of `TRANSFORMS(X)`) and that transform's data: `values` for `lookup`, `factor` for `scale-by`; none for a transform whose data is an owner's published mapping (`unit-id`, `designation-meaning`: [Lookup values the owners publish](#lookup-values-the-owners-publish)). Never code |
| `extension` | `true` | carried verbatim into the descriptor's `extensions.<format>.<field>` (a record of a control's or a port's scope under `<scope>/<field>`) |
| `dropped` | `{ ruling }` | left out, by the decision it names: a spec path and section, or the TERM's own `out-of-scope` mark |

A record of the plugin's scope whose row is a control's or a port's word (`controls[].*`, `ports[].*`) says that field of
the plugin, not of a control: LV2 lets a plugin carry its own `lv2:symbol`, and mda Piano does. It is carried as an
extension (`extensions.lv2.lv2:symbol`), never refused and never read as a control.

Each row names what it covers, one of two: `term`, a TERM of the format's domain (`LV2_UNITS_TERMS#unit`: plugin-db's domain lv2; CLAP's: omx-clap's domain clap), or
`from`, the header or specification link of a field no TERM file lists (the CLAP struct fields and `clap_entry`,
`rdf:type`, `rdfs:comment`, `rdfs:seeAlso`, `doap:name`, `doap:license`).

### Field names

The key of a row is the field as the dump names it:

- a CLAP TERM: its `id` (`CLAP_PARAM_IS_STEPPED`, `CLAP_EXT_LATENCY`, `CLAP_PLUGIN_FEATURE_DELAY`);
- a CLAP struct field: `<struct>.<member>` as the headers spell them (`clap_param_info.min_value`), or
  `<struct>.<function>` for what a call returns (`clap_plugin.get_extension`, `clap_plugin_params.value_to_text`);
- an LV2 TERM: `<prefix>:<term>`, the term's own name under the prefix of its specification (`units:db`,
  `lv2:toggled`, `pg:group`, `units:units.lv2` for the specification itself);
- any other LV2 predicate: its usual CURIE (`rdf:type`, `rdfs:comment`, `doap:name`).

The LV2 prefixes: `lv2` lv2core, `atom`, `bufsz` buf-size, `da` data-access, `dman` dynmanifest, `ev` event,
`ia` instance-access, `log`, `midi`, `morph`, `opts` options, `param` parameters, `patch`, `pg` port-groups,
`pprops` port-props, `pset` presets, `rsz` resize-port, `state`, `time`, `ui`, `units`, `urimap` uri-map, `urid`,
`work` worker; and `rdf`, `rdfs`, `doap`, `foaf` for the W3C and DOAP vocabularies.

### Field rows and value rows

Some TERMs are fields (`lv2:minimum`, `units:unit`); others are values a field takes (`units:db` is a value of
`units:unit`, `lv2:toggled` of `lv2:portProperty`, `CLAP_PARAM_IS_STEPPED` of `clap_param_info.flags`). Every TERM has
its row either way. A record of the dump is resolved in this order:

1. when its value is the key of a row (a value row): a `word` row converts it, a `dropped` row drops it, an `extension`
   row says the value has no word of its own and defers to the field's row;
2. otherwise the field's row: a `word` row converts the value (a `lookup` that has no entry for it carries the value
   in the bag instead), an `extension` row carries it in the bag, a `dropped` row drops it;
3. a field with no row at all is refused: `describe` names it and writes no descriptor.

A unit value row (`units:db`) and a designation value row (`param:gain`) hold no pair of their own: their transform
reads the one the format's owner publishes (next section), and where the TERM file names the unit's word, the owner's
mapping gives that word, which the coverage test holds.

### Lookup values the owners publish

A unit and a meaning are not this table's words, and the format's own spelling of them belongs to the package that owns
the format's level (plugin-hostd#215, row M5). A row that turns one into the other names, by its transform, the mapping
that owner publishes in its domain, and carries no `values`:

| Transform | Rows | The owner's mapping, read from the contract directory | Pair |
|---|---|---|---|
| `unit-id` | CLAP `omx_clap_param_contract_entry.unit` | omx-clap's domain `omx-param-contract`, the sheet `OMX_PARAM_CONTRACT_UNIT_IDS` | each code (`db`) -> its id (`dB`) |
| `unit-id` | LV2 `units:<unit>` value rows | plugin-db's domain `lv2`, the word of `LV2_UNIT_IDS` whose `x-from` names the row's TERM | the row's key (`units:db`) -> the word's `const` (`dB`) |
| `unit-id` | LV2 `units:unit` | plugin-db's domain `lv2`, every word of `LV2_OPENMIXER_UNIT_IDS` | its `x-uri` (`urn:openmixer:unit#dBFS`) -> its `const` (`dBFS`) |
| `designation-meaning` | LV2 `param:<term>` and `lv2:enabled` value rows | plugin-db's domain `lv2`, the word of `LV2_DESIGNATION_MEANINGS` whose `x-from` names the row's TERM | the row's key (`param:gain`) -> the word's `const` (`gain`) |

Each value is a JSON string. A unit's is a `PARAM_UNITS` id of omx-contract spelled as its standard symbol (`dB`, `Hz`,
`ms`, `percent`; never a lowercase key, an alias or a second accepted spelling), and the dimension that id carries in
`PARAM_UNITS` (`x-dimension`, `gain` for `dB`) is read there, never stored beside it (decision 2 of plugin-hostd#215,
ruled 2026-11-23). A plugin unit no owner maps to a standard id is a `dropped` row naming its ruling, never a new
spelling here.

`describe` reads each owner's domain, once, from the contract directory it was given (`--contract-dir`, else
`$OMX_CONTRACT_PATH`), and when that holds no such domain, from the installed one: a domain found but unreadable, a
document that is not that owner's (`$id`, `info.x-owner`), a mapping item that is absent, and a `unit-id` or
`designation-meaning` row for which the mapping holds no pair, are refused by name and no descriptor is written. The
inverse reads the same pairs backwards; a pair is one to one or refused, as a `lookup`.

### What a table drops

A row is `dropped` only by a decision it names. The TERMs their domain marks `out-of-scope` are dropped by that mark,
which the row quotes. A field this section rules out is dropped by `docs/formats.md#what-a-table-drops`:

- a runtime handle that is no fact of the plugin (`clap_param_info.cookie`, a pointer the host passes back);
- every field of the panel description (`omx_clap_plugin_panel_description.*` and the `omx_clap_panel_*` structures of
  omx-clap-core's `omx_clap_ext.h`): the panel travels whole, as the scan's `panel` object, by `panel_get`
  ([panel.md](panel.md)), and the descriptor carries none of it. A panel field's row is a drop and nothing else,
  but for one: a role's `omx_clap_panel_role.role` is the word `controls[].meaning` through `role-to-meaning`, the
  meaning the role plays given to the control its `param_id` names (omx-panel's `docs/panel-layout.md`, "Meanings and
  roles": a declared panel names the role, a descriptor the meaning). `describe` refuses a table that makes any other
  panel field a word or the bag, and the role field a word by any other transform.

A TERM its domain marks `used` is never dropped: its row is a word or the bag.

### Outbound-read rows

A generator reads a value row of a table to write a face: the TERM is a value (not a `property`) and omx-contract
lists omx-plugins among its users (`by`). Such a row's transform is `identity` or `lookup`, the two a generator applies
by reading the table alone, or `unit-id` or `designation-meaning`, which a generator applies by reading the same owner's
mapping backwards; what is structure (scale points, groups, module paths) stays in the generator's code.

## The transforms

`src/transforms.h` declares the closed list as one X-macro, `TRANSFORMS(X)`: the name a table writes, the inbound
function (format to descriptor) and its inverse (descriptor to format), all prefixed `transforms_`. A value crosses as
text: a JSON literal on the descriptor side (`-60`, `"dB"`, `true`, `["Filter","Envelope"]`), the dump's text on the
format side.

| Name | Inbound | Inverse | Data |
|---|---|---|---|
| `identity` | the value as it is, a number as a number | the same | none |
| `lookup` | the value's entry in `values` | the key whose entry it is | `values`, one to one: a table whose values repeat is refused |
| `scale-by` | the number times `factor` | the number divided by `factor` | `factor`, not zero |
| `flag` | present -> `true` | `true` -> the row's key, `false` -> nothing | none |
| `scale-points` | `<number> <label>` -> one point of the control's `values` and `labels` | the point back as `<number> <label>` | none |
| `group-path` | a CLAP module path `a/b` -> the group `["a","b"]` | the group joined by `/` | none |
| `port-group` | an LV2 group's label -> the group `["label"]`; a `pg:subGroupOf` label -> a level put before the group read so far | the path's last level, the group a port names | none |
| `role-to-meaning` | a declared panel's role -> the meaning it plays, from the contract directory's role tables; a role no package declares gives nothing (the meaning stays `unknown`) | the one role that plays the meaning; refused when two or more do | the contract directory's `roleMeanings` items, never the row's own `values` |
| `unit-id` | a unit as the format spells it -> its standard id, from the owner's mapping ([Lookup values the owners publish](#lookup-values-the-owners-publish)); a spelling the mapping lacks gives nothing (carried in the bag) | the spelling whose id it is | the owner's published unit mapping, never the row's own `values` |
| `designation-meaning` | an LV2 designation -> the standard meaning, from plugin-db's `LV2_DESIGNATION_MEANINGS` | the designation whose meaning it is | the owner's published mapping, never the row's own `values` |
| `output-symbol` | a CLAP meter's name -> the output symbol a host reads it by, omx-clap-core's rule (`doc/reference.md`): each byte outside `[A-Za-z0-9_]` is `_`, a leading digit gets a `_` before it; an empty name is refused | the symbol itself, refused when it is no symbol | none |

A new transform is added when a row needs it, never before; `make test-transforms` runs every function and its inverse
over its vectors (in, out, back in, equal).

## The coverage test

`make test-format-coverage` runs `tests/format_coverage.py` once per format. The field list is every term of the
format's TERMs, the items of its domain (`<contractdir>/lv2/lv2.json`, plugin-db's, for LV2; `<contractdir>/clap/clap.json`,
omx-clap's, for CLAP) plus every row with a `from`; each field has
exactly one row. It prints, per field, `mapped <word> <transform>`, `extension <format>` or `dropped <decision>`, then the
count per class. It is red for:

- a field with no row, and a row that covers no field (its `term` is no installed term);
- a `word` the descriptor schema lacks (walked in the installed `omx-contract.schema.json`), or a `lookup` entry that
  is no value the word takes;
- a `transform` that is not in `TRANSFORMS(X)`, or a `lookup` that is not one to one;
- a `used` TERM that is `dropped`, and a `dropped` row that names no decision;
- an outbound-read row whose transform is neither `identity` nor `lookup`;
- a unit row that does not map to the word its TERM names;
- a `unit-id` or `designation-meaning` row that carries `values`, whose owner's mapping holds no pair for it, or whose
  pair's value is no value the word takes; a `unit-id` value that is no `PARAM_UNITS` id of omx-contract's domain
  `param` or carries no dimension there;
- a row an owner's mapping covers written as a `lookup` with `values` of its own: any row of the word
  `controls[].travel.unit`, and an LV2 row whose TERM a word of `LV2_DESIGNATION_MEANINGS` names;
- a table item that is not an `x-kind` `map` of its format.

`tests/format_coverage.py --self-test` breaks a copy of each table three ways (one row removed, one `word` misspelt,
one transform renamed) and each arm must go red naming the field.

## The field dump

`omx-clap-scan --fields clap:<path>#<id> | lv2:<uri>` writes one record per line, TAB-separated:

```
<scope>	<field>	<value>
```

- `scope`: `plugin`; `param:<index>` (CLAP, in `clap_plugin_params.get_info` order); `audio_in:<index>`,
  `audio_out:<index>`, `note_in:<index>`, `note_out:<index>` (CLAP ports); `meter:<index>` (a CLAP meter of
  `clap.meters/1`, in `get_info` order); `port:<index>` (an LV2 port, by `lv2:index`). A scope is a source field's first segment, so a bag key `<scope>/<field>` is one too. A CLAP plugin
  that serves a panel description adds `panel`, `section:<index>`, `control:<index>`, `role:<index>`,
  `display:<index>` and `placement_default:<index>` (omx-clap-scan 0.20.0); these scopes are no entry of the
  descriptor, and each of their fields is dropped (above).
- `field`: a row key, as named above.
- `value`: the field's value as text. A number in `%.17g`; a CLAP constant (a flag bit, a port type, a note dialect,
  an extension id, a feature the headers define) by its macro name, one record per flag set or per item; an LV2 URI as
  a CURIE under the prefixes above, a URI no prefix covers in full; a scale point or a CLAP value text as
  `<number> <label>`. A TAB or a newline in a text becomes a space.
- the provenance: a CLAP dump writes `plugin	clap_entry	<file name of the .clap>`, an LV2 dump
  `plugin	rdfs:seeAlso	<bundle directory>/<data file>`, the `.ttl` that describes the plugin.

The first line is `# omx-clap-scan --fields 1`, the format's version; a dump with another version is refused.

## The descriptor `describe` writes

`plugin-hostd-probe describe [--table <file>] [--fields-from <dump.tsv>] [--contract-dir <dir>] clap:<path>#<id> | lv2:<uri>` writes the
`scanned` descriptor on stdout, exit 0; 2 when nothing is written (usage, a table it cannot read, a refused dump), 3 when
the dump cannot be made. Without `--fields-from` it runs `omx-clap-scan --fields` under the probe runner's limits, in a
child of its own (`run`'s isolation); with it, it reads a recorded dump, which is what its own tests do.

What the tables leave to `describe`:

- each scope is one entry: a CLAP `param:` scope a control, a CLAP port scope a port, an LV2 `port:` scope a control
  when a row makes it one (`lv2:ControlPort`) and a port when a row gives it a port kind; `id` and `name` follow the
  entry;
- an LV2 control's kind is `travel` (its `lv2:ControlPort` row) unless another record of the port gives a more
  specific one (`toggle`, `choice`, `trigger`), whatever order the dump lists the port's records in;
- an LV2 travel that states both `lv2:integer` (stepped) and `pprops:logarithmic` (log) is `log`, whatever order the
  dump lists them in;
- an LV2 output control is `readonly`; an LV2 port that reports latency (`lv2:latency`) is no control;
- consecutive LV2 audio ports of one direction, role and group are one port, its `channels` their count, its layout
  `mono` or `stereo` by that count;
- a CLAP port that is not main is `aux`; a control's `unit` is `unknown` when no row sets it, its `scale` `unknown`
  on CLAP and `linear` on LV2 (where a scale not stated is linear); its `meaning` is `unknown` when no row sets it; a
  control with points is a `choice`, its `ids` taken from its labels and its default the id of the default's point, a
  `toggle` defaults to the nearer of its two positions, true from 0.5 up;
- a scanned parameter's kind follows omx-contract's one rule (its `docs/descriptors.md`, "A scanned CLAP parameter's
  kind"), which `share/omx-contract/clap-kind-vectors.json` holds and `tests/describe_clap_kind_vectors_test.py` runs
  `describe` through, vector by vector: a parameter flagged an enumeration (`CLAP_PARAM_IS_ENUM`) or with value texts is
  a `choice`, whatever its range; else one whose merged scale is stepped (the contract entry's word when it has one, else
  `CLAP_PARAM_IS_STEPPED`), from 0 to 1, with a step of 1 (the contract entry's `step` when it states one; stepped means
  whole positions, so 1 is implied) is a `toggle`, CLAP stating a boolean in no other way, and a panel that draws it as a
  switch is right to; else a `travel` with the merged scale word. The same words read the same on LV2, where a port's
  own `lv2:toggled` or `pprops:trigger` record gives its kind before the rule is asked;
- a CLAP parameter's contract entry (`org.openmixer.param-contract/1`) gives its `symbol`, its unit (a contract unit
  `none` is the plugin stating none: `unknown`), its scale, and its `step` when the step is not 0 (0 is a continuous
  travel, written as no step);
- a CLAP `meter:` scope is one item of `meters[]` (omx-contract's `docs/descriptors.md`), in the plugin's order: a
  gain reduction's unit is `dB`, a level's `dBFS` (`clap.meters/1`'s kinds), and its `scale` is `unknown`, as an
  unstated CLAP scale is. A meter of a kind the descriptor has no word for (`CLAP_METER_KIND_OTHER`) is no item: its
  kind is carried in the bag (`meter:<index>/clap_meter_info.kind`) and nothing else of it is written. A meter of more than one channel answers to `<symbol>_<channel>` from 0, and a plugin
  whose meters give one output symbol twice, or one a parameter's `symbol` answers to, is refused naming the symbol,
  as omx-clap-core refuses it;
- a CLAP control's meaning from its declared panel's role: the role tables are the `roleMeanings` items of the
  contract directory (omx-contract's `docs/contract-dir.md`, "A package's role meanings"), read from
  `--contract-dir <dir>`, else `$OMX_CONTRACT_PATH`, else the directory plugin-hostd was built for, under its major:
  every package's `MANIFEST.json` and each `.json` file it lists, each checked against its hash. A role declared
  twice (`contract.role.duplicate`), a file that does not match its hash, a role whose `param_id` no parameter has, and
  two roles giving one parameter two meanings are refused. With no role table installed every meaning stays `unknown`;
  a role that plays none (`unknown`) leaves it so. The tests read the fixture directory
  `tests/fixtures/contract-dir`, never the machine's;
- an LV2 port's group path is its `pg:group` label with one `pg:subGroupOf` record per group above it, nearest first
  (the scanner follows the chain, `lv2:name` else `rdfs:label` of each group); the path is read outermost first, and a
  `pg:subGroupOf` with no `pg:group` before it is refused;
- the bag holds a field's one value as it is, two or more as a list;
- a plugin no feature of which maps is an `audio-effect`; an LV2 plugin's `id` and `uri` are the URI asked for;
- the links a scanned descriptor needs (`source.from`): a CLAP descriptor's own, `<file>#clap_entry`; each LV2
  control's, `<data file>#<symbol>`, from the row of `clap_entry` and of `rdfs:seeAlso`; a character a link cannot hold
  becomes `_`; `instrument` is written when the features hold it, `polyphonic` when it states more than one voice; `latency`
  is always written, `reports` false when no row sets it.
- a word of a table that `describe` does not write is refused with the table: a new word is code here first.

## The pages `describe --pages` writes

`plugin-hostd-probe describe --pages [--table <file>] [--fields-from <dump.tsv>] clap:<path>#<id> | lv2:<uri>` writes
the pages a host lists a plugin's controls in, one JSON document on stdout; the same exit codes as `describe`, since
it runs the same descriptor first and refuses as `describe` refuses.

A page is a run of `controls` (above), in their declared order, of one `group`; the controls that state no group of
their own are one further group, `null`, not left off. A group's controls are cut into pages of 8, the size
`remote_pages`/`remote_page_get` already cut an LV2 bundle's own groups into (`panel.md#drawing-a-panel-the-three-
verbs-together`): a group's first page its first 8 controls in declared order, its second the next 8, and so on.
Pages are written in the order their group first appears among the controls, a group's own pages consecutive and in
that order. Every control is on exactly one page, and the pages of one descriptor are the same on every run: this
holds whether or not a plugin groups its own controls, since the controls that state none are cut into pages the
same way, by the same declared order.

```json
{"pages": [
  {"group": ["Filter"], "params": [5]},
  {"group": null, "params": [3, 7]}
]}
```

- `group`: the page's controls' own `group` array, or `null` for the controls that state none;
- `params`: the `id` of each control on the page (`controls[].id`), in declared order.
