# The pins come from the qualification store: no pin file, no sync export

Status: RULED by the owner 2026-11-28: the ruling of section 1, and the six rulings of section 9 on the points this spec
put to the owner, which replace the recommendations it made where they differ. Settled: this spec is law for the pins of
plugin-hostd, plugin-db-qualification's reader, the qualification domain and plugin-qualify's sync and spool.

plugin-hostd keeps no design directory since the notes moved to openmixer.org (b50718fe); this spec is the first to
come back, because a settled spec is law and the change crosses five repositories: plugin-hostd (the reader of the
pins, and the owner of the qualification domain), plugin-db-qualification (the store and its reader library),
plugin-hostd-protocol (the settings table) and plugin-qualify (the store's writer: the sync and the quick-check spool).

## 1. The ruling

Owner, 2026-11-28, "the file and the sync step should go": plugin-hostd reads every plugin's pin (the SHA-256 of each
file it loads, its layout) and its verdict straight from the sqlite qualification store through
libplugin-qualification-db, as it already reads the costs there. The pin file `/var/lib/omx/qualified.pins` (the
default when the settings name no `pin_file`, plugin-hostd#316) and plugin-qualify-sync's step that exports the store's
verdicts into it are REMOVED. No compatibility path, no fallback to the file.

## 2. What the store holds, and what its reader does not give yet

The store (plugin-db-qualification `schema/qualification.sql`, user_version 2; its spec
`docs/design/specs/qualification-sqlite.md`, section 3.7 "Binary identity, the key's SHA-256 and the pin") already holds
every fact a pin needs. **No column is missing, so no migration**:

| a pin needs | the store holds it in | the reader gives it today |
| --- | --- | --- |
| the plugin, by format and id | `plugin.format`, `plugin.uri` (the CLAP id or the LV2 URI) | `pqdb_each` (query `format`, `uri`) |
| the main binary below its install root | `record.binary_path` (a `.clap`: its own file name) | `pqdb_each` (query `binary_path`) |
| every file the pin holds and its SHA-256 | `record_file (path, sha256)`, ascending by path, the list plugin-hostd's `--pin-files` names | `pqdb_files` |
| the layout | `record.layout_scheme`, `record.layout_sha256`; `record.unpinnable` | `pqdb_result.layout_*`, `.unpinnable` |
| the verdict of a host profile | `verdict (host, measured, rating)` | `pqdb_verdict_of` |
| why a conditional verdict is conditional | `reason (verdict_ord, rating, code)` | **nothing** |
| the isolated step and the pool step | `run_step (step, result)` | **nothing** |
| that the store changed | the layer files (base, and the scope's user layer) | **nothing** |

So the reader library gains two functions (section 5), and the store's schema does not change.

## 3. Every path of the daemon that reads the file, and what it reads after

| path | today | after |
| --- | --- | --- |
| `pin_mode strict` | admits a plugin pinned by `pin_set`, a `pin_file` (the default `/var/lib/omx/qualified.pins`) or `pins_dir` | `pin_set`, **the store**, `pins_dir` (ruling 1: no `pin_file`) |
| `pin_mode first-use`: the verdict of a learned pin | the learned pin (pin store) has none; it comes from a `pin_file` line or a `pins_dir` pin with a verdict | **the store's record of the files the daemon hashed**, or a `pins_dir` pin with a verdict |
| R-112: a bypassed insert going live | the tick reads a changed `pin_file`/`pins_dir` and promotes the inserts whose pin now carries a verdict | the same, and a changed store is a change (section 6) |
| the spool's verdict pins (`<pins_dir>/90-qualify-spool.pins`, plugin-qualify-spool) | read as a `pins_dir` file | none: the spool's verdict is a record in the store (ruling 2) |
| `pin_accept` and `<pin_store>.accepted` | the user's choice over a refusal of `pins_dir` or the `pin_file` | the user's choice over a refusal of `pins_dir` **or the store**, kept the same way |
| `pin_reload` and the tick's re-read | stat of the `pin_file` and the `pins_dir` files | stat of the `pins_dir` files and of a named `pin_file`, and `pqdb_changed` of the store (section 6) |

## 4. The store layer: which record is a uri's pin

A layer of its own, read only, between the controller's `pin_set` and the host's other pins:

1. **The lookup.** For the uri of an `add` the daemon collects the files the format loads (`pin_collect`, the list
   `--pin-files` prints) and hashes each. It asks the store for the records of the plugin: the format, the id (the CLAP
   id after `#`, or the LV2 URI; both spellings of an IRI, as `qualcost` asks) and, for a CLAP, `binary_path` = the
   `.clap` file's own name. A record is the uri's when its file list is exactly the files hashed: the same paths, the
   same SHA-256 each, none missing, none beside them (store spec 3.7: the match is on the hashes alone; the record's
   set, class and name decide nothing). A record that is `unpinnable` or holds no layout gives no pin.
2. **The pin** is the record's list and layout, and the verdict and pool words of `pqdb_pin_of` (section 5) under the
   host profile `omx-clap-host` (ruling 3), with the history adjustment of the daemon's class (ruling 6).
3. **Several records match** (two offers, two classes, the base and the user layer under different keys): the worst
   verdict stands, `refused` over `isolated` over `in-process` over none, as plugin-qualify's pin file kept it ("a
   plugin found twice is never pinned more kindly than its worst measurement"); a pool word stands only when every
   matching record that gives a verdict other than `refused` says `cores`.
4. **Precedence.** A `pins_dir` refusal holds over everything but the user's choice, as today. Then a controller's
   `pin_set`. Then the store layer, which holds over a pin the daemon learned (the learned pin is what it hashed for
   the check it asked for; the store's record of those files is the check's answer) and over a named `pin_file`'s pin.
   Then the host's other pins, then the `pins_dir` pins, as today. A store refusal is overridden by `pin_accept`
   (first-use only) where the check reads the choice (`pins_check`), as a `pin_file` refusal was.
5. **No record** of those bytes: the store layer gives nothing and the daemon goes on as with no pin file, so under
   first-use the plugin is learned and its quick check requested (R-112), and under strict it is `-508`.

The store is opened by the daemon's scope, as `qualcost` opens it: `PQDB_SCOPE_SYSTEM` as root, `PQDB_SCOPE_USER`
otherwise; the test build opens the file `PLUGIN_HOSTD_TEST_QUALIFICATION_STORE` names. A store that cannot be opened is
said once on stderr by its `qualification-db.*` name and gives no pin, never a start that fails.

## 5. What the reader library gains (plugin-db-qualification)

- `int pqdb_pin_of(const pqdb *db, const pqdb_result *r, const char *host, pqdb_pin *out)`: the words the record's pin
  carries for one host profile, `out->verdict` (`in-process`, `isolated`, `refused`, or NULL) and `out->pool` (`cores`,
  `off`, or NULL). 0; 1 when the record gives no whole pin (unpinnable, or no layout). The rule, one place, from the
  stored rows, in this order:
  1. the host's verdict: not measured, `unknown` or none: no word; `unsuitable`: `refused`; `suitable`: `in-process`;
     `conditional`: `in-process` when it has at least one reason of rating `conditional` and every such reason's code is
     a groupable one, else `isolated`. The groupable codes are `hosting.rt-safety.own-threads` (D20, plugin-qualify's
     the qualification domain's `QUALIFICATION_GROUPABLE_CONDITIONAL_CODES`, ruling 5);
  2. the record's `isolated` step, when it has one: `isolated` makes the word `isolated`, `refused` makes it `refused`,
     `not-run` leaves no word (plugin-qualify's `pinAfterStep`);
  3. the record's `pool` step: `cores` or `off` is the pool word, none for a `refused` verdict (`pinAfterPool`).
- `int pqdb_changed(const pqdb *db)`: 1 when a layer the handle opened is no longer the file it opened (device, inode,
  size or modification time of the file or of its `-wal`), or a layer that was absent at the open now exists; 0
  otherwise. It opens nothing and reads no row, so a daemon may call it at every idle tick.

Both are exported in the library's map and its Debian symbols, a minor raise of the library.

## 6. Noticing a store change without a restart

Today the daemon stats the `pin_file` and the `pins_dir` files at every idle tick and before every `add`, and reads
them again when one changed. After: the daemon keeps one store handle for its pins, opened at the first lookup. At every
idle tick and before every `add` it asks `pqdb_changed`; a change closes the handle and forgets every pin the store
layer gave, then does what a changed `pins_dir` does now: the running instances are checked against the pins as they
are (one the new pins refuse keeps running and is marked `!` in `worker_list`), and the bypassed inserts whose pin now
carries a verdict go live (R-112). `pin_reload` does the same at once. The sync's `pin_changed` notice and its
`pin_set` of every changed pin are no longer needed (section 7).

## 7. What is removed

- **plugin-hostd**: the default `/var/lib/omx/qualified.pins` (`HOSTD_DEFAULT_PIN_FILE`, `default_pin_file`,
  `pins_file_optional`, the test seam `PLUGIN_HOSTD_TEST_DEFAULT_PIN_FILE`); settings that name no `pin_file` read
  none. The guide's paragraph on the default, and every sentence that has the qualification sync write a pin file.
- **plugin-qualify**: plugin-qualify-sync's `pin_file` setting and `--pin-file` flag, the pin file it writes
  (`syncPinsText`), and the `pin_set`/`pin_clear` it sends the daemon's command port for each changed pin
  (`hostd_port`, `hostd_feedback_port`): the same export by another door, which the store change of section 6 replaces.
  The sync still writes the records, with the list plugin-hostd's `--pin-files` names (store spec 3.7), and that is
  how a verdict reaches the daemon.

No compatibility path: an installed `/var/lib/omx/qualified.pins` is a file nothing reads; the packages that wrote it
remove it on upgrade.

## 8. What stays, and why

- **`pin_set`**: a controller's pin, held over the store, kept over a reload. A host that pins by itself (`pin_mode
  strict` with its own controller) and the tests need it; it writes no file.
- **`pins_dir`**: the packages' read-only layer. A package that ships a plugin may ship its pin with it, before any
  store record exists, removed with the package; and its `refused` is the distribution's word, which only the user
  overrides.
- **The first-use pin store** (`$XDG_STATE_HOME/plugin-hostd/pins`): what the daemon hashed on a first add of a plugin
  no record names, the files its R-112 request carries and the files a later verdict is about. The store holds
  measurements; the pin store holds what this machine saw before any measurement.
- **`pin_accept` and `<pin_store>.accepted`**: the user's choice over a refusal, the daemon's alone; it now covers a
  store refusal too.

## 9. The owner's rulings (2026-11-28), in force

1. **`pin_file` is removed entirely.** The pins come only from the qualification store, a controller's `pin_set` and the
   packages' read-only `pins_dir`. The setting leaves plugin-hostd-protocol's settings table; a settings line naming
   `pin_file` is refused by name (`bad setting 'pin_file'`) and the daemon does not start. Sections 3, 4, 7 and 8's
   sentences on a named `pin_file` are void.
2. **The quick-check spool writes its verdict into the store**, through the store's writer, never as a pin file in
   `pins_dir`; `pins_dir` holds the packages' pins alone. plugin-qualify-spool qualifies a request with
   `plugin-qualify-sync --plugin <uri>`, the one-plugin qualification that puts the record; the daemon reads it at its
   next tick (section 6). A run that the spool's budget or the memory limit ends writes no record: the plugin stays
   bypassed (R-112) until `pin_accept`, and the request is answered in the spool alone.
3. **The verdicts are read under the fixed host profile `omx-clap-host`**, with no setting, for now.
4. **`cores` is a word of `QUALIFICATION_STEP_RESULTS`** (the qualification domain, plugin-hostd's `contract.d`, its
   `info.version` 0.1.1 to 0.1.2: its own word change). The writer stores a pool step that ended `cores`, the reader
   returns it, and a store pin carries `pool=cores` (plugin-db-qualification's `test/test_pool_round_trip.sh`).
5. **The qualification domain declares the groupable reason codes once**: `QUALIFICATION_GROUPABLE_CONDITIONAL_CODES`
   (since 0.1.2). plugin-qualify's rule and the store's reader read them from the domain; no source holds a copy, and a
   test in each fails on one.
6. **The daemon reads the history-adjusted verdict as the store records it**: `pqdb_pin_of` applies the latest adjust
   block (`record_history`, `history_verdict.adjusted`) of the daemon's history class (the `host_class` setting, else
   the class of the machine) that holds a verdict of `omx-clap-host`, after the isolated step and before the pool word.

## 10. Red-first tests

- plugin-db-qualification: `pqdb_pin_of` gives each word of the rule from fixture rows (suitable; conditional with a
  groupable reason only; conditional with another; unsuitable; unknown; not measured; an isolated step of each result;
  a pool step of each result; a refused verdict with a `cores` pool step; unpinnable; no layout); `pqdb_changed` is 0
  on an untouched store, 1 after a rename over the base, 1 after a write in place, 1 after an absent user layer appears.
- plugin-hostd: under strict, a plugin whose bytes a store record holds is admitted with no `pin_file`; a record of other
  bytes admits nothing (`-509`/`-508`); a `refused` record refuses the add (`-516`); an `isolated` record runs it in a
  worker of its own and an `in-process` one shares; under first-use, a bypassed insert goes live when a record of its
  files is written into the store while the daemon runs, with no restart and no `pin_reload`; `pin_accept` overrides a
  store refusal; settings that name no `pin_file` read no `/var/lib/omx/qualified.pins`.
- plugin-qualify: a sync writes no pin file and sends no `pin_set`; its settings know no `pin_file`.
