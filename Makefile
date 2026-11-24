# compiler
CC ?= gcc

# program names
PROG = plugin-hostd
VERSION = $(shell sed -n "s/^Version: *//p" packaging/plugin-hostd.spec)
FAKE = tests/fake-host
# LD_PRELOAD into the daemon under test: fsync as slow as a disk under contention (tests/slow_fsync.c)
SLOW_FSYNC = tests/slow-fsync.so
# LD_PRELOAD into the daemon under test: scandir lists in the order the bundle rule's test sets (tests/scandir_listing.c)
SCANDIR_LISTING = tests/scandir-listing.so
FORMAT_TEST = tests/format-test
HISTORY_TEST = tests/history-test
PROC_TEST = tests/proc-test
PROC_TERM_TEST = tests/proc-term-test
CONF_TEST = tests/conf-test
PLANNER_TEST = tests/planner-test
PLACEMENT_TEST = tests/placement-test
QUALCOST_TEST = tests/qualcost-test
RELAY_TEST = tests/relay-test
GESTURE_ALLOC_TEST = tests/gesture-alloc-test
LV2_ALLOC_TEST = tests/lv2-alloc-test
VERBS_ALLOC_TEST = tests/verbs-alloc-test
TRANSFORMS_TEST = tests/transforms-test
PROBE = plugin-hostd-probe
PROBE_LOCK = plugin-hostd-probe-lock.so

PKG_CONFIG ?= pkg-config

# a plugin-hostd-protocol checkout, used when pkg-config finds no installed plugin-hostd-protocol
PROTOCOL_DIR ?= ../plugin-hostd-protocol

# the protocol library, plugin-hostd-protocol: pkg-config when it is installed, a checkout of it otherwise. Beside the
# library: the scenario corpus and the source of its runner (the jack test), and the protocol page the verb table is
# read from
ifeq ($(shell $(PKG_CONFIG) --exists plugin-hostd-protocol && echo true), true)
PROTOCOL_CFLAGS = $(shell $(PKG_CONFIG) --cflags plugin-hostd-protocol)
PROTOCOL_LIBS = $(shell $(PKG_CONFIG) --libs plugin-hostd-protocol)
PROTOCOL_SCENARIOS = $(shell $(PKG_CONFIG) --variable=scenarios plugin-hostd-protocol)
PROTOCOL_RUNNER = $(shell $(PKG_CONFIG) --variable=runner plugin-hostd-protocol)
PROTOCOL_PAGE = $(shell $(PKG_CONFIG) --variable=protocoldoc plugin-hostd-protocol)
PROTOCOL_JSON = $(shell $(PKG_CONFIG) --variable=protocoljson plugin-hostd-protocol)
MODHOST_JSON = $(shell $(PKG_CONFIG) --variable=modhostjson plugin-hostd-protocol)
else
PROTOCOL_LIB = $(PROTOCOL_DIR)/libplugin-hostd-protocol.so
PROTOCOL_CFLAGS = -I$(PROTOCOL_DIR)/include
# the checkout's library is not installed: the binary finds it there through its rpath
PROTOCOL_LIBS = -L$(PROTOCOL_DIR) -lplugin-hostd-protocol -Wl,-rpath,$(abspath $(PROTOCOL_DIR))
PROTOCOL_SCENARIOS = $(PROTOCOL_DIR)/tests/host-scenarios.txt
PROTOCOL_RUNNER = $(PROTOCOL_DIR)/tests/host_scenarios.c
PROTOCOL_PAGE = $(PROTOCOL_DIR)/doc/protocol.md
PROTOCOL_JSON = $(PROTOCOL_DIR)/protocol/plugin-hostd.json
MODHOST_JSON = $(PROTOCOL_DIR)/protocol/mod-host.json
endif

# The declared protocol is plugin-hostd-protocol's (0.5.0 or later, before 0.6), never this tree's: <plugin-hostd/protocol.h> and
# the headers it includes are found through PROTOCOL_CFLAGS, after this tree's -Iinclude (which holds the
# vocabulary of data/, and in a scratch tree of tests/sabotage.py a changed copy of the protocol headers); the JSON of
# protocol.h (PROTOCOL_JSON) and mod-host's (MODHOST_JSON) are its files. make check-no-protocol-copy fails when a copy
# of any of them is back in this tree.
PROTOCOL_INCLUDE = $(firstword $(foreach d,$(patsubst -I%,%,$(filter -I%,$(PROTOCOL_CFLAGS))),$(if $(wildcard $(d)/plugin-hostd/protocol.h),$(d))))
# what is built from them depends on them, and on a scratch copy of them in include/plugin-hostd/ where one is
PROTOCOL_HEADERS = $(wildcard include/plugin-hostd/*.h $(PROTOCOL_INCLUDE)/plugin-hostd/*.h)

# omx-contract's C header (omx-contract-devel, libomx-contract-dev): the protocol's
# parameter scales are read from it; CONTRACT_CFLAGS=-I<dir> for a header that is not installed
CONTRACT_CFLAGS ?= $(shell $(PKG_CONFIG) --cflags omx-contract 2>/dev/null)
# omx-dsp's rendered definitions (omx-dsp-devel, libomxdsp-dev): the probe runner's default rates are its ORACLE_FLOOR_RATES
# (the oracle rates left omx-contract for omx-dsp); its include directory only, none of its floating-point flags
OMXDSP_CFLAGS ?= $(shell $(PKG_CONFIG) --cflags-only-I omxdsp 2>/dev/null)

# the qualification store's reader, plugin-qualification-db (<plugin-qualification-db/pqdb.h>): pkg-config when it is installed, a
# checkout of it otherwise (PQDB_DIR, its library built in place). Its DDL builds the fixtures of the tests: the installed
# one (pkg-config --variable=schema), else PQDB_SCHEMA, else the checkout's schema/qualification.sql; the daemon reads the store through the library only, never a file of records
PQDB_DIR ?= ../plugin-db-qualification
ifeq ($(shell $(PKG_CONFIG) --exists plugin-qualification-db && echo true), true)
PQDB_CFLAGS = $(shell $(PKG_CONFIG) --cflags plugin-qualification-db)
PQDB_LIBS = $(shell $(PKG_CONFIG) --libs plugin-qualification-db)
PQDB_SCHEMA ?= $(shell $(PKG_CONFIG) --variable=schema plugin-qualification-db)
else
PQDB_CFLAGS = -I$(PQDB_DIR)/include
PQDB_LIBS = -L$(PQDB_DIR) -lplugin-qualification-db -Wl,-rpath,$(abspath $(PQDB_DIR))
PQDB_SCHEMA ?= $(PQDB_DIR)/schema/qualification.sql
endif

# CLAP headers for the test plugin: pkg-config when clap-devel is installed, CLAP_CFLAGS=-I<dir> otherwise
CLAP_CFLAGS ?= $(shell $(PKG_CONFIG) --cflags clap 2>/dev/null)

# cJSON (cjson-devel, libcjson-dev): what reads every JSON document here, the probe runner's child lines and the format tables
CJSON_CFLAGS ?= $(shell $(PKG_CONFIG) --cflags libcjson)
CJSON_LIBS ?= $(shell $(PKG_CONFIG) --libs libcjson)

# default compiler and linker flags
CFLAGS += $(CJSON_CFLAGS)
CFLAGS += -O2 -Wall -Wextra -std=gnu99 -fPIC -D_GNU_SOURCE -pthread -Wno-format-truncation
CFLAGS += -Werror=implicit-function-declaration -Werror=return-type

ifeq ($(DEBUG), 1)
   CFLAGS += -O0 -g -DDEBUG
else
   CFLAGS += -fvisibility=hidden
   LDFLAGS += -s
endif

# <plugin-db/pin.h>: the pins, the layout digests, and what its SHA-256 links (plugin-db.pc requires libcrypto)
PIN_CFLAGS := $(shell $(PKG_CONFIG) --cflags plugin-db)
PIN_LIBS := $(shell $(PKG_CONFIG) --libs plugin-db)
INCS = -Iinclude $(PROTOCOL_CFLAGS) $(PIN_CFLAGS) $(DOMAIN_CFLAGS) $(PQDB_CFLAGS)

# the machine domain (contract.d/machine/) and the qualification domain (contract.d/qualification/) are
# read at start-up through omx-contract's C loader (libomx-domain) (src/domain_words.c, src/machine.c,
# src/qualification_words.c); of the machine domain only the codes of the items marked x-c-codes (the band counts and the
# family ids of src/machine.h) are rendered, include/plugin-hostd/machine_codes.h. The probe and the generator read OMX_CONTRACT_PATH (their test entry: a ':' list, the first
# directory holding the domain wins) and the daemon the installed contract directory only; the tests of this tree run the
# CLIs over this checkout's own documents, the installed contract directory after it
DOMAIN_CFLAGS ?= $(shell $(PKG_CONFIG) --cflags libomx-domain 2>/dev/null)
DOMAIN_LIBS ?= $(shell $(PKG_CONFIG) --libs libomx-domain 2>/dev/null)
INSTALLED_CONTRACT_DIR := $(shell $(PKG_CONFIG) --variable=contractdir omx-contract 2>/dev/null)
export OMX_CONTRACT_PATH := $(strip $(OMX_CONTRACT_PATH)$(if $(strip $(OMX_CONTRACT_PATH)),:)$(CURDIR)/contract.d$(if $(INSTALLED_CONTRACT_DIR),:$(INSTALLED_CONTRACT_DIR)))

LDFLAGS += -Wl,--no-undefined

# source and object files
SRC = src/main.c src/conf.c src/proc.c src/confine.c src/supervisor.c src/verbs.c src/pins.c src/pin_words.c src/relay.c src/formats.c src/lv2.c \
      src/descriptors.c src/describe.c src/transforms.c src/json.c src/fsutil.c src/writer.c src/domain_words.c src/machine.c src/history.c src/planner.c src/qualcost.c src/placement.c src/session.c src/words.c
OBJ = $(SRC:.c=.o)

# the C names of the words of this tree's domains plugin-hostd/grouping and plugin-hostd/history (contract.d/plugin-hostd/), rendered by omx-contract
# (render-verbs below); the daemon's verbs and reply codes are rendered in plugin-hostd-protocol, beside protocol.h
RENDERED = include/plugin-hostd/plugin_hostd_vocabulary.h
# the error words of the extension errors: every refusal number the protocol declares a code for, written at build time
# from plugin-hostd-protocol's JSON of the protocol (beside PROTOCOL_JSON) and never committed (src/session.c)
.DEFAULT_GOAL := all
REPLY_WORDS = src/reply_words.h
$(REPLY_WORDS): $(dir $(PROTOCOL_JSON))plugin-hostd-protocol.json tools/reply-words.py
	python3 tools/reply-words.py $< > $@.tmp && mv $@.tmp $@

# default build
all: $(PROG) $(PROBE) $(PROBE_LOCK)

$(PROG): $(OBJ) $(PROTOCOL_LIB)
	$(CC) $(OBJ) $(PROTOCOL_LIBS) $(LDFLAGS) -pthread $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) -lm -o $@

# the test build of the daemon, never installed or packaged: src/main.c compiled with OMX_CONTRACTDIR, the one directory it
# reads the machine domain from (the packaged daemon reads the installed contract directory only, no path and no
# environment variable). TEST_CONTRACT_TREE is the checkout's contract.d/machine installed as the loader reads it;
# tests/contract-empty holds no domain, for the refusal arm of tests/machine_domain.py
TEST_CONTRACT_TREE = $(CURDIR)/tests/contract-tree
TEST_CONTRACT_EMPTY = $(CURDIR)/tests/contract-empty
TEST_OBJ = $(filter-out src/main.o,$(OBJ)) src/main-test.o
TEST_OBJ_EMPTY = $(filter-out src/main.o,$(OBJ)) src/main-test-empty.o
PROG_TEST = tests/plugin-hostd-test
PROG_TEST_EMPTY = tests/plugin-hostd-test-empty

$(TEST_CONTRACT_TREE): $(wildcard contract.d/machine/*)
	@test -n "$(INSTALL_CONTRACT_DIR)" || { echo "$@: no install-contract-dir.sh: install omx-contract-devel, or set INSTALL_CONTRACT_DIR or OMX_CONTRACT_DIR" >&2; exit 1; }
	rm -rf $@
	sh $(INSTALL_CONTRACT_DIR) --domain contract.d/machine $(TEST_CONTRACT_TREE)

$(TEST_CONTRACT_EMPTY):
	mkdir -p $@

# and with OMX_QUALIFICATION_TEST_STORE, the other seam of the test builds: the qualification store is read from the file
# PLUGIN_HOSTD_TEST_QUALIFICATION_STORE (pqdb_open_at) instead of the installed one, so each test has a
# store of its own (tests/qual_fixture.py). A packaged daemon is built with neither: it opens the store of its scope (pqdb_open)
# and reads no path and no environment variable
src/main-test.o: src/main.c $(TEST_CONTRACT_TREE)
	$(CC) $(INCS) $(CFLAGS) -DOMX_CONTRACTDIR='"$(TEST_CONTRACT_TREE)"' -DOMX_QUALIFICATION_TEST_STORE -c -o $@ src/main.c

src/main-test-empty.o: src/main.c $(TEST_CONTRACT_EMPTY)
	$(CC) $(INCS) $(CFLAGS) -DOMX_CONTRACTDIR='"$(TEST_CONTRACT_EMPTY)"' -DOMX_QUALIFICATION_TEST_STORE -c -o $@ src/main.c

$(PROG_TEST): $(TEST_OBJ) $(PROTOCOL_LIB)
	$(CC) $(TEST_OBJ) $(PROTOCOL_LIBS) $(LDFLAGS) -pthread $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) -lm -o $@

$(PROG_TEST_EMPTY): $(TEST_OBJ_EMPTY) $(PROTOCOL_LIB)
	$(CC) $(TEST_OBJ_EMPTY) $(PROTOCOL_LIBS) $(LDFLAGS) -pthread $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) -lm -o $@

# the probe runner: it loads no plugin and links nothing of the daemon or of the protocol library
# describe reads the installed table of a format by default (docs/formats.md)
PROBE_SRC = src/probe.c src/confine.c src/probe_cgroup.c src/json.c src/describe.c src/transforms.c src/machine.c src/probe_words.c src/scan_words.c src/domain_words.c src/qualification_words.c
$(PROBE): $(PROBE_SRC) src/confine.h src/probe_cgroup.h src/json.h src/describe.h src/pages.h src/transforms.h src/machine.h src/probe_words.h src/scan_words.h src/domain_words.h src/qualification_words.h src/probe_lock.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) -Iinclude $(PROTOCOL_CFLAGS) $(PIN_CFLAGS) -Isrc $(CONTRACT_CFLAGS) $(OMXDSP_CFLAGS) $(DOMAIN_CFLAGS) $(CFLAGS) -D_GNU_SOURCE -DPROBE_VERSION='"$(VERSION)"' \
	  -DPROBE_CONTRACTDIR='"$(CONTRACTDIR)"' -DPROBE_CONTRACT_MAJOR='"$(CONTRACT_SCHEMA_MAJOR)"' \
	  -DPROBE_LOCK_PRELOAD='"$(LIBEXECDIR)/plugin-hostd/probe-lock.so"' -o $@ $(PROBE_SRC) -lm $(PIN_LIBS) $(DOMAIN_LIBS) $(CJSON_LIBS)

# the probe's lock preload (src/probe_lock.c): preloaded into the measured child only, it locks the child's memory before
# its main; installed where the runner looks for it by default, $(LIBEXECDIR)/plugin-hostd/probe-lock.so
$(PROBE_LOCK): src/probe_lock.c src/probe_lock.h
	$(CC) $(CFLAGS) -shared -o $@ src/probe_lock.c $(LDFLAGS)

ifneq ($(PROTOCOL_LIB),)
$(PROTOCOL_LIB):
	$(MAKE) -C $(PROTOCOL_DIR) libplugin-hostd-protocol.so
endif

# the declared protocol is compiled into every object
$(OBJ) src/main-test.o src/main-test-empty.o: $(PROTOCOL_HEADERS) $(RENDERED) $(REPLY_WORDS)

# the host class of the history is the probe's machine class: the machine domain's band words; the JSON string literals of the
# daemon and the probe are spelled by omx-contract's one writer, <omxcontract/omx_json_write.h> (check-no-json-escape-loop)
src/machine.o src/json.o src/transforms.o: INCS += $(CONTRACT_CFLAGS)

src/descriptors.o: src/descriptors.h src/describe.h src/json.h src/formats.h src/supervisor.h
src/describe.o src/lv2.o: src/pages.h

# meta-rule to generate the object files
%.o: %.c
	$(CC) $(INCS) $(CFLAGS) -c -o $@ $<

# install rule
PREFIX = /usr/local
BINDIR = $(PREFIX)/bin

MANDIR = $(PREFIX)/share/man/man1

DATADIR = $(PREFIX)/share
INCLUDEDIR = $(PREFIX)/include
LIBEXECDIR = $(PREFIX)/libexec

install: $(PROG) $(PROBE) $(PROBE_LOCK) install_man install_protocol install_machine_domain install_qualification_domain install_vocabulary_domains install_tests
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 $(PROG) $(DESTDIR)$(BINDIR)
	install -m 755 $(PROBE) $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)$(LIBEXECDIR)/plugin-hostd
	install -m 644 $(PROBE_LOCK) $(DESTDIR)$(LIBEXECDIR)/plugin-hostd/probe-lock.so

# what this tree declares beside the protocol (the protocol itself is plugin-hostd-protocol's): the schemas of the probe
# output and of a preset file, the pin header and the vocabulary of data/, their pkg-config file, and the pins_dir other
# packages drop their pins in
install_protocol:
	install -d $(DESTDIR)$(DATADIR)/plugin-hostd
	install -m 644 protocol/probe-output.schema.json $(DESTDIR)$(DATADIR)/plugin-hostd/probe-output.schema.json
	install -m 644 protocol/preset.schema.json $(DESTDIR)$(DATADIR)/plugin-hostd/preset.schema.json
	install -d $(DESTDIR)$(DATADIR)/plugin-hostd/pins.d
	install -d $(DESTDIR)$(INCLUDEDIR)/plugin-hostd
	install -m 644 $(RENDERED) $(DESTDIR)$(INCLUDEDIR)/plugin-hostd/
	install -d $(DESTDIR)$(DATADIR)/pkgconfig
	sed -e 's,@PREFIX@,$(PREFIX),g' -e 's,@VERSION@,$(VERSION),g' -e 's,@PROTOCOL_FLOOR@,$(shell tools/dep-floor.sh plugin-hostd-protocol-devel),g' -e 's,@PLUGIN_DB_FLOOR@,$(shell tools/dep-floor.sh plugin-db-devel),g' protocol/plugin-hostd.pc.in > $(DESTDIR)$(DATADIR)/pkgconfig/plugin-hostd.pc
	chmod 644 $(DESTDIR)$(DATADIR)/pkgconfig/plugin-hostd.pc

# the domain machine (contract.d/machine: its document and its catalogs), installed to <contractdir>/machine/ by the
# domain mode of omx-contract's installer and by nothing else, no copy of ours: plugin-hostd-contract ships it.
# INSTALL_CONTRACT_DIR (below) names the installer: omx-contract's own when installed, a checkout's otherwise
.PHONY: install_machine_domain
install_machine_domain:
	@test -n "$(INSTALL_CONTRACT_DIR)" || { echo "install_machine_domain: no install-contract-dir.sh: install omx-contract-devel, or set INSTALL_CONTRACT_DIR or OMX_CONTRACT_DIR" >&2; exit 1; }
	sh $(INSTALL_CONTRACT_DIR) --domain contract.d/machine $(DESTDIR)$(CONTRACTDIR)

# the domain qualification (contract.d/qualification: what a qualification measures and records, with its catalogs; plugin-qualify's
# up to its 1.4.0), installed to <contractdir>/qualification/ the same way: plugin-hostd-contract ships it, and the probe and the
# schema generator refuse to start without it (78)
.PHONY: install_qualification_domain
install_qualification_domain:
	@test -n "$(INSTALL_CONTRACT_DIR)" || { echo "install_qualification_domain: no install-contract-dir.sh: install omx-contract-devel, or set INSTALL_CONTRACT_DIR or OMX_CONTRACT_DIR" >&2; exit 1; }
	sh $(INSTALL_CONTRACT_DIR) --domain contract.d/qualification $(DESTDIR)$(CONTRACTDIR)

# the domains the vocabulary renders (VOCABULARY_DOMAINS: plugin-hostd/grouping, plugin-hostd/history) and the domains of the
# format tables (FORMAT_DOMAINS: plugin-hostd/clap, plugin-hostd/lv2, each a sheet whose value is the map { format, rows }
# of docs/formats.md), installed to <contractdir>/<domain>/ the same way: plugin-hostd-contract ships them, and a reader
# of the words (plugin-hostd-protocol's clients) or of the tables (omx-plugins' generators) reads them there
FORMAT_DOMAINS = plugin-hostd/clap plugin-hostd/lv2
# the top-level domains of this tree (installed by install_machine_domain and install_qualification_domain), the ones its MANIFEST.json names
OWNER_DOMAINS = machine qualification
.PHONY: install_vocabulary_domains
install_vocabulary_domains:
	@test -n "$(INSTALL_CONTRACT_DIR)" || { echo "install_vocabulary_domains: no install-contract-dir.sh: install omx-contract-devel, or set INSTALL_CONTRACT_DIR or OMX_CONTRACT_DIR" >&2; exit 1; }
	for d in $(VOCABULARY_DOMAINS) $(FORMAT_DOMAINS); do sh $(INSTALL_CONTRACT_DIR) --domain contract.d/$$d $(DESTDIR)$(CONTRACTDIR) || exit 1; done

# the package plugin-hostd of omx-contract's contract directory, <contractdir>/<schema major>/plugin-hostd/: a MANIFEST.json
# naming this version and no file (this tree's contract is domains alone: the install script's --owner form), which is
# also what tells omx-contract's reader that the directory <contractdir>/plugin-hostd/ holds the domains
# plugin-hostd/<name> and is no domain of its own. The manifest lists the owner's top-level domains (OWNER_DOMAINS): the
# reader takes a domain name of one segment there, so plugin-hostd/clap and the other nested domains are not listed.
# plugin-hostd-contract ships it with the domains. contractdir and the
# install script are omx-contract-devel's; a checkout of omx-contract (OMX_CONTRACT_DIR) stands in for the script when
# it is not installed. The schema major is omx-contract's, read from its pkg-config file (schema_major, omx-contract 3.9.0
# or later) and never typed here: a recipe that needs it fails naming the missing variable when no omx-contract-devel
# answers, while a target that does not need it (fuzz, the checks) still runs without one.
CONTRACT_SCHEMA_MAJOR_PC := $(shell $(PKG_CONFIG) --variable=schema_major omx-contract 2>/dev/null)
CONTRACT_SCHEMA_MAJOR = $(or $(CONTRACT_SCHEMA_MAJOR_PC),$(error CONTRACT_SCHEMA_MAJOR: pkg-config names no schema_major of omx-contract: install omx-contract-devel 3.9.0 or later))
CONTRACTDIR = $(or $(shell $(PKG_CONFIG) --variable=contractdir omx-contract 2>/dev/null),$(DATADIR)/omx-contract/contract.d)
INSTALL_CONTRACT_DIR = $(firstword $(wildcard $(shell $(PKG_CONFIG) --variable=datadir omx-contract 2>/dev/null)/install-contract-dir.sh) $(wildcard $(OMX_CONTRACT_DIR)/tools/install-contract-dir.sh))

.PHONY: install-contract
install-contract:
	@test -n "$(INSTALL_CONTRACT_DIR)" || { echo "install-contract: no install-contract-dir.sh: install omx-contract-devel, or set OMX_CONTRACT_DIR to a checkout" >&2; exit 1; }
	sh $(INSTALL_CONTRACT_DIR) --owner $(PROG) $(VERSION) $(CONTRACT_SCHEMA_MAJOR) $(DESTDIR)$(CONTRACTDIR) $(OWNER_DOMAINS)

# the contract directory as a reader of it sees it: the domains and install-contract into a staging directory, then omx-contract validate
# of the staged package and domains together with the installed contract directory (omx-contract's own tables, omx-clap-core's),
# red on any table the installed schema refuses (#165; tests/format_coverage.py walks the schema for the words, never
# for the row keys). An absent omx-contract command is red, never a skip
.PHONY: check-contract-dir
check-contract-dir:
	@command -v $(OMX_CONTRACT) >/dev/null || { echo "$@: no $(OMX_CONTRACT) command: install omx-contract 3.2.0 or later" >&2; exit 1; }
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf $$tmp' EXIT; \
	$(MAKE) --no-print-directory install_machine_domain install_qualification_domain install_vocabulary_domains install-contract DESTDIR=$$tmp >/dev/null; \
	OMX_CONTRACT_PATH=$$tmp$(CONTRACTDIR)$(if $(OMX_CONTRACT_PATH),:$(OMX_CONTRACT_PATH)):$(CONTRACTDIR) $(OMX_CONTRACT) validate --installed

# the words of this tree's domains (VOCABULARY_DOMAINS), rendered by omx-contract as the package installs them, beside the packages of
# OMX_CONTRACT_PATH and of the installed contract directory: the C names the planner and the history read
# (plugin_hostd_vocabulary.h). `make render-verbs` writes them and records the omx-contract that rendered them
# (RENDERED_WITH), `make check-rendered` fails on any drift. A package build sets RENDERED_COMPARE=recorded: with
# another omx-contract than the recorded one installed the render is not compared and the check says so, so a tag
# builds the same after the channel moves on (#120); the default compares always. The daemon's verbs are
# plugin-hostd-protocol's, rendered there.
OMX_CONTRACT ?= omx-contract
# the grouping words are the domain plugin-hostd/grouping (contract.d/plugin-hostd/grouping): the planner's reasons are its
# words in its order, the vocabulary header is its render byte for byte, a renamed word in a scratch domain is the
# render's and the planner's, and plugin-hostd-protocol's Python client holds the same words (tests/grouping_domain.py)
.PHONY: test-grouping-domain test-history-domain
# the history keys are the domain plugin-hostd/history the same way: history_line writes its words in its order, the
# header is its render, a renamed key in a scratch domain is history_line's (tests/history_domain.py)
test-history-domain:
	OMX_CONTRACT='$(OMX_CONTRACT)' INSTALL_CONTRACT_DIR='$(INSTALL_CONTRACT_DIR)' \
	  CC='$(CC)' CFLAGS='$(PROTOCOL_CFLAGS) $(PIN_CFLAGS) $(CONTRACT_CFLAGS) $(DOMAIN_CFLAGS) $(CFLAGS)' \
	  LIBS='$(PROTOCOL_LIBS) $(PIN_LIBS) $(DOMAIN_LIBS) -lm' python3 tests/history_domain.py
test-grouping-domain: tests/planner-test
	OMX_CONTRACT='$(OMX_CONTRACT)' INSTALL_CONTRACT_DIR='$(INSTALL_CONTRACT_DIR)' \
	  CC='$(CC)' CFLAGS='$(CFLAGS) $(INCS)' python3 tests/grouping_domain.py
# the format tables are the domains plugin-hostd/clap and plugin-hostd/lv2: sheets holding their rows as data/formats did, installed
# to <contractdir>/plugin-hostd/<format>/, and read by describe from the domain's document (tests/format_domains.py)
.PHONY: test-format-domains
test-format-domains: $(PROBE)
	PROBE=./$(PROBE) MAKE='$(MAKE)' python3 tests/format_domains.py
# the domains whose words the vocabulary renders (contract.d/<domain>, each item's x-file the data path it came from):
# omx-contract's render reads each with --with-domain (repeated), rebuilding its data files into the package this tree
# installs, so the vocabulary renders as its data form did, its banner naming each domain's document
VOCABULARY_DOMAINS = plugin-hostd/grouping plugin-hostd/history
RENDERED_WITH = $(RENDERED).rendered-with
RENDERED_COMPARE ?= always
.PHONY: render-verbs check-rendered
render-verbs check-rendered:
	@test -n "$(INSTALL_CONTRACT_DIR)" || { echo "$@: no install-contract-dir.sh: install omx-contract-devel, or set OMX_CONTRACT_DIR to a checkout" >&2; exit 1; }
	@renderer=$$($(PKG_CONFIG) --modversion omx-contract 2>/dev/null); recorded=$$(cat $(RENDERED_WITH) 2>/dev/null || true); \
	if [ $@ = check-rendered ] && [ "$(RENDERED_COMPARE)" = recorded ] && [ -n "$$recorded" ] && [ "$$renderer" != "$$recorded" ]; then \
	  echo "$(RENDERED) is rendered with omx-contract $$recorded; $$renderer is installed: not compared"; exit 0; fi; \
	set -e; tmp=$$(mktemp -d); trap 'rm -rf $$tmp' EXIT; \
	for d in $(OWNER_DOMAINS); do sh $(INSTALL_CONTRACT_DIR) --domain contract.d/$$d $$tmp >/dev/null; done; \
	sh $(INSTALL_CONTRACT_DIR) --owner $(PROG) $(VERSION) $(CONTRACT_SCHEMA_MAJOR) $$tmp $(OWNER_DOMAINS) >/dev/null; \
	OMX_CONTRACT_PATH=$$tmp$(if $(OMX_CONTRACT_PATH),:$(OMX_CONTRACT_PATH)):$(CONTRACTDIR) \
	  $(OMX_CONTRACT) render --target c --package $(PROG) --installed $(foreach d,$(VOCABULARY_DOMAINS),--with-domain contract.d/$(d)) --out include/plugin-hostd $(if $(filter check-rendered,$@),--check); \
	if [ $@ = render-verbs ]; then test -n "$$renderer" || { echo "$@: pkg-config names no omx-contract version" >&2; exit 1; }; \
	  echo "$$renderer" > $(RENDERED_WITH); fi

# the machine domain's codes header (include/plugin-hostd/machine_codes.h) is the render of the items marked x-c-codes
# (MACHINE_CORE_BANDS, MACHINE_CLOCK_BANDS, MACHINE_FAMILIES; src/machine.h takes its counts and ids from it): validate,
# fmt --check and render --check
.PHONY: check-machine-codes
# (the machine domain, staged alone (the probe domain is plugin-hostd-protocol's): the qualification domain names plugin-hostd-protocol's domain pin, which a
# directory read alone cannot see; it is validated with the installed contract directory by check-contract-dir and
# tests/qualification_pin_from.py)
check-machine-codes:
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf $$tmp' EXIT; cp -r contract.d/machine $$tmp/; \
	$(OMX_CONTRACT) validate --contract-dir $$tmp; \
	$(OMX_CONTRACT) fmt --check --contract-dir $$tmp; \
	$(OMX_CONTRACT) render --target c --package machine --contract-dir $$tmp --out include/plugin-hostd --check

# the machine domain is a valid document, the codes header is its render, and the installed tree opens through the
# loader (tests/machine_domain.py; DOMAIN_CFLAGS and DOMAIN_LIBS name a loader that pkg-config does not find)
.PHONY: test-machine-domain
test-machine-domain: $(PROBE) $(PROG_TEST) $(PROG_TEST_EMPTY) tools/protocol-gen tests/probe-child tests/stress.clap
	OMX_CONTRACT='$(OMX_CONTRACT)' INSTALL_CONTRACT_DIR='$(INSTALL_CONTRACT_DIR)' PROBE=./$(PROBE) GEN=./tools/protocol-gen DAEMON=$(abspath $(PROG_TEST)) DAEMON_EMPTY=$(abspath $(PROG_TEST_EMPTY)) \
	  DOMAIN_CFLAGS='$(DOMAIN_CFLAGS)' DOMAIN_LIBS='$(DOMAIN_LIBS)' CONTRACT_CFLAGS='$(CONTRACT_CFLAGS)' python3 tests/machine_domain.py

# the probe domain (plugin-hostd-protocol's, read from its contract package) holds exactly the words the probe writes, the
# probe and the generated schema write the domain's words, and a missing or short one is refused by name at start-up (tests/probe_domain.py)
.PHONY: test-probe-domain
test-probe-domain: $(PROBE) tools/protocol-gen tests/probe-child tests/stress.clap
	OMX_CONTRACT='$(OMX_CONTRACT)' INSTALL_CONTRACT_DIR='$(INSTALL_CONTRACT_DIR)' PROBE=./$(PROBE) GEN=./tools/protocol-gen \
	  PROTOCOL_HEADER='$(PROTOCOL_INCLUDE)/plugin-hostd/protocol.h' DOMAIN_CFLAGS='$(DOMAIN_CFLAGS)' DOMAIN_LIBS='$(DOMAIN_LIBS)' python3 tests/probe_domain.py

# the probe words are plugin-hostd-protocol's domain and this tree reads them from there (tests/probe_owner_test.py)
.PHONY: test-probe-owner
test-probe-owner:
	PROTOCOL_HEADER='$(PROTOCOL_INCLUDE)/plugin-hostd/protocol.h' DOMAIN_CFLAGS='$(DOMAIN_CFLAGS)' DOMAIN_LIBS='$(DOMAIN_LIBS)' python3 tests/probe_owner_test.py

# a release build is reproducible at its tag (#120): tests/rendered_at_tag.sh
.PHONY: test-rendered-at-tag
test-rendered-at-tag:
	bash tests/rendered_at_tag.sh

# the tables cover their format (tests/format_coverage.py, docs/formats.md#the-coverage-test): every TERM of the format's
# domain (plugin-db's lv2, omx-clap's clap) and every row with a from, once per format, each field one row; then its
# sabotage arms, each red naming its field, among them a scratch domain without a term a row maps
.PHONY: test-format-coverage
test-format-coverage:
	python3 tests/format_coverage.py --contract-dir $(CONTRACTDIR) --major $(CONTRACT_SCHEMA_MAJOR) clap
	python3 tests/format_coverage.py --contract-dir $(CONTRACTDIR) --major $(CONTRACT_SCHEMA_MAJOR) lv2
	python3 tests/format_coverage.py --contract-dir $(CONTRACTDIR) --major $(CONTRACT_SCHEMA_MAJOR) --self-test

# the fake worker and the protocol clients (lib/protocol.sh, lib/plugin_hostd_client.py), for a program that drives plugin-hostd: away from $(BINDIR), where nothing runs it by chance
install_tests: $(FAKE)
	install -d $(DESTDIR)$(LIBEXECDIR)/plugin-hostd/tests
	install -m 755 $(FAKE) $(DESTDIR)$(LIBEXECDIR)/plugin-hostd/tests/fake-host
	install -d $(DESTDIR)$(LIBEXECDIR)/plugin-hostd/tests/lib
	install -m 644 tests/lib/protocol.sh tests/lib/plugin_hostd_client.py $(DESTDIR)$(LIBEXECDIR)/plugin-hostd/tests/lib

install_man:
	install -d $(DESTDIR)$(MANDIR)
	install -m 644 doc/*.1 $(DESTDIR)$(MANDIR)

# The declared protocol is plugin-hostd-protocol's: no copy of its tables, its JSON, its headers or their generators is
# back in this tree, and no header here declares what protocol.h declares (tests/no_protocol_copy.py, with its
# --self-test, which plants each kind of copy in a scratch tree and must see it red)
check-no-protocol-copy:
	python3 tests/no_protocol_copy.py
	python3 tests/no_protocol_copy.py --self-test

# The JSON string literals of the daemon and the probe are spelled by omx-contract's one writer,
# <omxcontract/omx_json_write.h>: no C file of this tree carries an escape loop of its own (tests/no_json_escape_loop.py,
# with its --self-test, which plants each shape of loop in a scratch tree and must see it red)
check-no-json-escape-loop:
	python3 tests/no_json_escape_loop.py
	python3 tests/no_json_escape_loop.py --self-test

# An item's x-since is the version of its domain document that added it, never a release of a package or of omx-contract
# (tests/domain_x_since.py, with its --self-test, which plants each wrong x-since in a scratch copy and must see it red)
check-domain-x-since:
	python3 tests/domain_x_since.py
	python3 tests/domain_x_since.py --self-test

# No tracked file points into a private repository, issue, branch or path: Open-Mixer/.github's private-refs check, from a
# checkout of it (FREEMIXER_DOTGITHUB, else ../freemixer-dotgithub); CI runs it through the public-sources-check workflow.
FREEMIXER_DOTGITHUB ?= ../freemixer-dotgithub
.PHONY: private-refs check-no-protocol-copy check-no-json-escape-loop check-domain-x-since
private-refs:
	$(FREEMIXER_DOTGITHUB)/.github/actions/private-refs-check/check.sh .

# libFuzzer harnesses (fuzz/README.md): the command parser and dispatcher, src/verbs.c with the mod-host side replaced by
# a recorder, and the reply stream, src/relay.c with its sockets answered by the harness; clang with libFuzzer,
# AddressSanitizer and UndefinedBehaviorSanitizer, into build/fuzz/. Nothing of the ordinary build is touched.
#   make fuzz                  build every harness
#   make fuzz-run FUZZ_TIME=60 fuzz each one from its seed corpus; red on any crash
#   make fuzz-sabotage         each mutant of fuzz/sabotage/ must make its harness abort on a seed, in its own property
#   make fuzz-records          each check's mutant: record must make that check abort on its input: seed
#   make fuzz-coverage         the coverage witness: llvm-cov over the corpus, held to fuzz/coverage-floor.txt
#   make fuzz-corpus           write fuzz/corpus/ again from the declared protocol and the guide's examples
FUZZ_CC        ?= clang
FUZZ_TIME      ?= 60
FUZZ_BUILD     := build/fuzz
FUZZ_HARNESSES := command reply
FUZZ_SAN       := -fsanitize=address,undefined -fno-sanitize-recover=all
FUZZ_CFLAGS    := -O1 -g -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -fno-omit-frame-pointer
FUZZ_INCS      := -Iinclude -Isrc -Ifuzz $(PROTOCOL_CFLAGS) $(PIN_CFLAGS)
# what each harness is built from beside its own file: the command harness links the parser and the recorder, the
# reply harness includes src/relay.c itself
FUZZ_SRC_command := src/verbs.c src/session.c src/words.c src/pin_words.c src/writer.c src/fsutil.c fuzz/recorder.c
FUZZ_SRC_reply   :=
FUZZ_DEPS        := src/pin_words.c fuzz/fuzz.h fuzz/syntax.h fuzz/recorder.h src/relay.c src/verbs.h src/session.h $(REPLY_WORDS) $(PROTOCOL_HEADERS) $(RENDERED)

# the fuzz harnesses and what they are built from need no OpenSSL: they link none, and OSS Verify's builder, which builds
# them for its enrolment (theorem-labs/oss-verify#183), has no OpenSSL headers. Each source is compiled with an
# openssl/evp.h that fails put before every other include directory
test-fuzz-no-openssl: $(REPLY_WORDS)
	@set -e; for f in $(FUZZ_HARNESSES:%=fuzz/fuzz_%.c) $(FUZZ_SRC_command); do \
	  $(CC) -std=c11 -D_GNU_SOURCE -Werror -fsyntax-only -Itests/no-openssl $(FUZZ_INCS) $$f; \
	done
	@echo "ok   the fuzz harnesses and their sources build with no OpenSSL header"

$(FUZZ_BUILD)/fuzz_%: fuzz/fuzz_%.c $(FUZZ_DEPS) $(FUZZ_SRC_command)
	@mkdir -p $(dir $@)
	$(FUZZ_CC) $(FUZZ_CFLAGS) $(FUZZ_SAN) -fsanitize=fuzzer $(FUZZ_INCS) $< $(FUZZ_SRC_$*) -pthread -o $@ $(PIN_LIBS) $(PROTOCOL_LIBS)

fuzz: $(FUZZ_HARNESSES:%=$(FUZZ_BUILD)/fuzz_%)

fuzz-run: fuzz
	FUZZ_BUILD=$(FUZZ_BUILD) FUZZ_TIME=$(FUZZ_TIME) fuzz/run.sh $(FUZZ_HARNESSES)

fuzz-sabotage:
	FUZZ_BUILD=$(FUZZ_BUILD) MAKE="$(MAKE)" fuzz/sabotage.sh

# every check's comment names a one-line change and the seed on which that check aborts, or why it is not a property;
# each change is applied alone to the plain harness (fuzz/records.sh)
fuzz-records:
	FUZZ_BUILD=$(FUZZ_BUILD) FUZZ_CC=$(FUZZ_CC) PROTOCOL_CFLAGS="$(PROTOCOL_CFLAGS)" PROTOCOL_LIBS="$(PROTOCOL_LIBS)" PIN_CFLAGS="$(PIN_CFLAGS)" fuzz/records.sh

# the coverage witness: the same harnesses without sanitizers, instrumented for llvm-cov, each run once over its seed
# corpus (-runs=0 executes the corpus and nothing else); the llvm-cov and llvm-profdata of FUZZ_CC's own LLVM
FUZZ_COV_BUILD := $(FUZZ_BUILD)/cov
FUZZ_COV_FLAGS := -O0 -g -std=c11 -D_GNU_SOURCE -fprofile-instr-generate -fcoverage-mapping
LLVM_COV       ?= llvm-cov
LLVM_PROFDATA  ?= llvm-profdata

$(FUZZ_COV_BUILD)/fuzz_%: fuzz/fuzz_%.c $(FUZZ_DEPS) $(FUZZ_SRC_command)
	@mkdir -p $(dir $@)
	$(FUZZ_CC) $(FUZZ_COV_FLAGS) -fsanitize=fuzzer $(FUZZ_INCS) $< $(FUZZ_SRC_$*) -pthread -o $@ $(PIN_LIBS) $(PROTOCOL_LIBS)

fuzz-coverage: $(FUZZ_HARNESSES:%=$(FUZZ_COV_BUILD)/fuzz_%)
	@set -e; for h in $(FUZZ_HARNESSES); do \
	  rm -f $(FUZZ_COV_BUILD)/$$h.profraw; \
	  LLVM_PROFILE_FILE=$(FUZZ_COV_BUILD)/$$h.profraw $(FUZZ_COV_BUILD)/fuzz_$$h -runs=0 fuzz/corpus/$$h/ \
	      >$(FUZZ_COV_BUILD)/$$h.log 2>&1 || \
	    { cat $(FUZZ_COV_BUILD)/$$h.log; echo "fuzz-coverage: fuzz_$$h failed on its own corpus"; exit 1; }; \
	  $(LLVM_PROFDATA) merge -sparse $(FUZZ_COV_BUILD)/$$h.profraw -o $(FUZZ_COV_BUILD)/$$h.profdata; \
	done
	@LLVM_COV=$(LLVM_COV) fuzz/coverage.sh $(FUZZ_COV_BUILD) $(FUZZ_HARNESSES)

# the seed corpus is written from plugin-hostd-protocol's JSON of the protocol and of mod-host's (PROTOCOL_JSON,
# MODHOST_JSON) and the send lines of docs/guide.md and docs/own-host.md, never from a network, and committed;
# fuzz-corpus-check fails when it is not what they give
fuzz-corpus:
	PROTOCOL_JSON=$(PROTOCOL_JSON) MODHOST_JSON=$(MODHOST_JSON) python3 fuzz/gen_corpus.py fuzz/corpus

fuzz-corpus-check:
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf $$tmp' EXIT; \
	PROTOCOL_JSON=$(PROTOCOL_JSON) MODHOST_JSON=$(MODHOST_JSON) python3 fuzz/gen_corpus.py $$tmp; diff -r $$tmp fuzz/corpus; echo "the seed corpus is current"

.PHONY: fuzz fuzz-run fuzz-sabotage fuzz-records fuzz-coverage fuzz-corpus fuzz-corpus-check

# clean rule
clean:
	@rm -f src/*.o $(REPLY_WORDS) $(PROG) $(PROG_TEST) $(PROG_TEST_EMPTY) $(PROBE) $(PROBE_LOCK) tests/probe-child tests/lv2-probe-child tests/rt_interpose.so tests/sched-refuse.so tests/plugin-hostd-plan-refused tests/plan-refused.out $(FAKE) $(SLOW_FSYNC) $(SCANDIR_LISTING) $(HISTORY_TEST) $(PROC_TEST) $(PROC_TERM_TEST) $(CONF_TEST) $(PLANNER_TEST) $(QUALCOST_TEST) $(RELAY_TEST) tests/relay-test-relay.o $(FORMAT_TEST) tests/plugin-hostd-alloc-fail $(GESTURE_ALLOC_TEST) $(LV2_ALLOC_TEST) tests/lv2-alloc-lv2.o $(VERBS_ALLOC_TEST) $(TRANSFORMS_TEST) $(GEN) tests/stress.clap tests/jack_levels tests/host_scenarios $(LV2_FIXTURE) $(PLACEMENT_TEST)
	@rm -rf build $(TEST_CONTRACT_TREE) $(TEST_CONTRACT_EMPTY) tests/alloc-fail-objs tests/plan-refused-objs

# the daemon against workers that are not plugin hosts at all (tests/fake-host speaks the same protocol and can be
# made to die on cue): placement, forwarding, ledger, replay, attribution, the storm bound; no jack, no plugin
# SHA-256 is libcrypto's (plugin-db's pin.h, EVP_Digest): no tracked C source or header carries one of its own, found by the first
# of FIPS 180-4's round constants; the sabotage arm runs the same search over a planted copy, which must find it
SHA256_K0 = 0x428a2f98
.PHONY: test-no-sha256-copy
test-no-sha256-copy:
	@if git grep -nIi -e $(SHA256_K0) -- '*.c' '*.h' '*.S'; then echo "FAIL a SHA-256 of the tree's own; the digest is libcrypto's"; exit 1; fi
	@set -e; t=$$(mktemp -d); trap 'rm -rf $$t' EXIT; git init -q $$t; printf 'static const unsigned k[] = { 0x428A2F98 };\n' > $$t/sha.h; \
	git -C $$t add sha.h; if git -C $$t grep -qIi -e $(SHA256_K0) -- '*.c' '*.h' '*.S'; then :; else \
	  echo "FAIL the sabotage arm: a planted SHA-256 is not found"; exit 1; fi
	@echo "ok   SHA-256 is libcrypto's, and a planted copy is found"

test: test-bounded-install test-bundle-rule test-no-sha256-copy test-fuzz-no-openssl test-protocol-lib test-plan-refused test-sabotage-pool test-history test-proc test-proc-term test-conf test-own-host-probe-teardown test-voices-cores-diag test-planner test-placement test-transforms test-format-coverage test-describe test-describe-pages test-relay test-alloc test-alloc-sweep test-format test-ready-connect test-ready-connect-sabotage test-bind test-bind-sabotage test-daemon test-timing-load test-verbs-declared check-rendered test-rendered-at-tag test-grouping-domain test-format-domains check-generated check-no-protocol-copy check-no-json-escape-loop check-domain-x-since test-probe-schema test-vocabulary test-machine-domain test-probe-domain check-machine-codes test-probe-owner test-qualification-domain test-qualification-domain-owned test-qualification-pin-from test-probe test-contract test-consumer test-consumer-errors test-perturbation check-readme check-own-host-page check-no-pins check-no-test-seam check-ci-guards test-socket check-preset-schema test-install-schemas check-contract-floor check-floors-only check-readme-facts test-pin-files test-search-path check-no-moved-packages
	PROTOCOL_DIR=$(PROTOCOL_DIR) PROTOCOL_PAGE=$(PROTOCOL_PAGE) python3 tests/verbs_contract.py

# the protocol clients plugin-hostd-tests ships (tests/lib/), against a peer that frames by NUL, and their sabotage
# every package manager step in CI bounded: a hung mirror is a fast red naming it, never a hang to the job's timeout
.PHONY: test-bounded-install
test-bounded-install:
	python3 tests/bounded_install_test.py

.PHONY: test-protocol-lib
test-protocol-lib:
	python3 tests/protocol_lib.py

# the pool tests/sabotage.py runs its arms in: their order, their trees, their ports, and one run side by side against one after the other
.PHONY: test-sabotage-pool
test-sabotage-pool:
	python3 tests/sabotage_pool_test.py

# the first connect after the ready line, many starts, no retry (issue 238)
test-ready-connect: $(PROG_TEST) $(FAKE)
	PLUGIN_HOSTD=./$(PROG_TEST) FAKE_HOST=./$(FAKE) python3 tests/ready_connect_test.py

# the same test against a daemon whose ready line goes out before its sockets exist: it must fail (issue 238)
.PHONY: test-ready-connect test-ready-connect-sabotage
test-ready-connect-sabotage: $(PROG_TEST) $(FAKE) $(TEST_CONTRACT_TREE)
	python3 tests/ready_connect_sabotage.py ./$(PROG_TEST) $(FAKE) "$(CC)" "$(CFLAGS) $(INCS) -DOMX_CONTRACTDIR='\"$(TEST_CONTRACT_TREE)\"' -DOMX_QUALIFICATION_TEST_STORE" "$(OBJ)" "$(PROTOCOL_LIBS) $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) $(LDFLAGS)"

# who reaches the ports: 127.0.0.1 by default, other addresses only when asked (tests/bind_test.py), and the same test
# against a daemon built with each guard taken out, which must fail
.PHONY: test-bind test-bind-sabotage
test-bind: $(PROG_TEST) $(FAKE)
	PLUGIN_HOSTD=./$(PROG_TEST) FAKE_HOST=./$(FAKE) python3 tests/bind_test.py
test-bind-sabotage: $(PROG_TEST) $(FAKE) $(TEST_CONTRACT_TREE)
	python3 tests/bind_sabotage.py ./$(PROG_TEST) $(FAKE) "$(CC)" "$(CFLAGS) $(INCS) -DOMX_CONTRACTDIR='\"$(TEST_CONTRACT_TREE)\"' -DOMX_QUALIFICATION_TEST_STORE" "$(OBJ)" "$(PROTOCOL_LIBS) $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) $(LDFLAGS)"

# the same without the verb table, which is read from the protocol page (PROTOCOL_PAGE)
test-daemon: $(PROG_TEST) $(FAKE) $(SLOW_FSYNC)
	PLUGIN_HOSTD=./$(PROG_TEST) FAKE_HOST=./$(FAKE) python3 tests/daemon_test.py

# a timing proof reads the load (ruling 2026-11-11): on a node loaded past its cores a missed bound warns, naming the
# load, for the gate to rerun on a quiet node; on a quiet node it fails (tests/timing_load_test.py, with a fake load)
test-timing-load:
	python3 tests/timing_load_test.py

# the declared verbs on the daemon's socket (tests/verbs_declared.py): each answers its declared reply and codes, the
# daemon answers no undeclared word itself, and a verb both hosts owe answers in one shape from both; omx-clap-core's
# declarations come from OMX_CONTRACT_PATH or the installed contract directory
test-verbs-declared: $(PROG_TEST) $(PROBE) $(FAKE)
	PLUGIN_HOSTD=./$(PROG_TEST) PROBE=./$(PROBE) FAKE_HOST=./$(FAKE) python3 tests/verbs_declared.py

# panel_get on the wire against the installed omx-clap-scan (omx-clap-core 0.20.0 or later) and real plugins: one that
# publishes a panel (omx-plugins-clap's omx-delay) and one that publishes none (omx-clap-host-tests' fake compressor)
test-panel-wire: $(PROG_TEST) $(PROBE) $(FAKE)
	PLUGIN_HOSTD=./$(PROG_TEST) PROBE=./$(PROBE) FAKE_HOST=./$(FAKE) python3 tests/panel_wire.py

$(FAKE): tests/fake_host.c src/verbs.h $(PROTOCOL_LIB)
	$(CC) $(INCS) $(CFLAGS) -Werror -o $@ $< $(PROTOCOL_LIBS) $(PIN_LIBS) -lm

$(SLOW_FSYNC): tests/slow_fsync.c
	$(CC) $(CFLAGS) -Werror -shared -o $@ $< -ldl

$(SCANDIR_LISTING): tests/scandir_listing.c
	$(CC) $(CFLAGS) -Werror -shared -o $@ $<

# the command socket's framing, by omx-clap-core's socket_conformance.py. Which copy runs, in this order: the one
# SOCKET_CONFORMANCE names; ../omx-clap-core/tests/socket_conformance.py when an omx-clap-core checkout sits beside
# this one (a developer working on both runs the script being changed); else the one omx-clap-host-tests installs.
# The run prints the path it used.
SOCKET_CONFORMANCE ?= $(firstword $(wildcard ../omx-clap-core/tests/socket_conformance.py) /usr/libexec/omx-clap-host/tests/socket_conformance.py)
test-socket: $(PROG_TEST)
	PLUGIN_HOSTD=./$(PROG_TEST) SOCKET_CONFORMANCE=$(SOCKET_CONFORMANCE) ./tests/socket_e2e.sh

# a format registered only by the test goes through add, param, pin and remove; a row with a capability missing is refused
test-format: $(FORMAT_TEST) $(FAKE)
	PLUGIN_HOSTD_FORMAT_TEST_DIR=$${TMPDIR:-$${XDG_RUNTIME_DIR:-.}} ./$(FORMAT_TEST) ./$(FAKE)

# the daemon's parts without its main and its verbs: format_test calls the supervisor as the verbs do
FORMAT_OBJ = $(filter-out src/main.o src/verbs.o,$(OBJ))

$(FORMAT_TEST): tests/format_test.c $(FORMAT_OBJ) $(PROTOCOL_LIB)
	$(CC) $(INCS) -Isrc $(CFLAGS) -Werror -o $@ tests/format_test.c $(FORMAT_OBJ) $(PROTOCOL_LIBS) -pthread $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) -lm


# the running history (src/history.c, the grouping-planner design note): its line grammar, its file, what its
# counts and its summary come to, against records written out by hand; and the host class it is kept under (src/machine.c)
test-history: $(HISTORY_TEST)
	./$(HISTORY_TEST)

$(HISTORY_TEST): tests/history_test.c src/history.c src/words.c src/words.h src/history.h src/fsutil.c src/fsutil.h src/writer.c src/writer.h src/machine.c src/machine.h src/domain_words.c src/domain_words.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) -Iinclude $(PROTOCOL_CFLAGS) $(PIN_CFLAGS) -Isrc $(CONTRACT_CFLAGS) $(DOMAIN_CFLAGS) $(CFLAGS) -Werror -o $@ tests/history_test.c src/history.c src/words.c src/fsutil.c src/writer.c src/machine.c src/domain_words.c $(PROTOCOL_LIBS) $(PIN_LIBS) $(DOMAIN_LIBS) -lm

# tests/own_host_lv2_probe.py closes its JACK client on every exit path: run against a fake libjack whose realtime thread
# keeps firing the callback, a probe that skips the close dies with SIGSEGV at interpreter teardown
.PHONY: test-own-host-probe-teardown
test-own-host-probe-teardown:
	python3 tests/own_host_lv2_probe_teardown_test.py

# tools/zynthian/voices-cores.py says why a run failed: the server's or the host's exit status and last log lines (#8)
.PHONY: test-voices-cores-diag
test-voices-cores-diag:
	python3 tests/voices_cores_diag.py

# src/proc.c's readers of /proc: the text the kernel writes, and this process's own files
test-proc: $(PROC_TEST)
	./$(PROC_TEST)

$(PROC_TEST): tests/proc_test.c src/proc.c src/confine.c src/proc.h src/confine.h src/conf.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) $(INCS) -Isrc $(CFLAGS) -Werror -o $@ tests/proc_test.c src/proc.c src/confine.c -pthread $(PIN_LIBS) -lm

# a worker the daemon gives up on is sent SIGTERM and has two seconds to leave before SIGKILL (src/proc.c)
.PHONY: test-proc-term
test-proc-term: $(PROC_TERM_TEST)
	./$(PROC_TERM_TEST)

$(PROC_TERM_TEST): tests/proc_term_test.c src/proc.c src/confine.c src/conf.c src/proc.h src/confine.h src/conf.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) $(INCS) -Isrc $(CFLAGS) -Werror -o $@ tests/proc_term_test.c src/proc.c src/confine.c src/conf.c -pthread $(PIN_LIBS) $(CJSON_LIBS) -lm

# the search settings (src/conf.c, plugin-hostd-protocol's plugin-hostd/search_paths.h): the default lists, $LV2_PATH, lv2_extra, $CLAP_PATH
test-conf: $(CONF_TEST)
	./$(CONF_TEST)
	python3 tests/search_paths_once.py

$(CONF_TEST): tests/conf_test.c src/conf.c src/conf.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) $(INCS) -Isrc $(CFLAGS) -Werror -o $@ tests/conf_test.c src/conf.c $(PIN_LIBS)

# the grouping planner (src/planner.c, the grouping-planner design note), on its own: each reason it gives, the order its
# rules decide in, the text of a plan, and that the same members give the same bytes
test-planner: $(PLANNER_TEST) $(QUALCOST_TEST)
	./$(PLANNER_TEST)
	./$(QUALCOST_TEST)

# the fixtures are built from plugin-qualification-db's schema (tests/qual_fixture.py); the word check of the unknown-word arm
# reads this checkout's machine domain, installed as the loader reads it
$(QUALCOST_TEST): tests/qualcost_test.c tests/qual_fixture.py src/qualcost.c src/qualcost.h src/json.c src/json.h $(PROTOCOL_HEADERS) $(RENDERED) $(TEST_CONTRACT_TREE)
	$(CC) -Isrc $(PROTOCOL_CFLAGS) $(CONTRACT_CFLAGS) $(PQDB_CFLAGS) $(CFLAGS) -Werror \
	    -DQUAL_SCHEMA='"$(abspath $(PQDB_SCHEMA))"' -DQUAL_FIXTURE='"$(abspath tests/qual_fixture.py)"' \
	    -DQUALCOST_SOURCE='"$(abspath src/qualcost.c)"' -DTEST_CONTRACT_TREE='"$(TEST_CONTRACT_TREE)"' \
	    -o $@ tests/qualcost_test.c src/qualcost.c src/json.c $(PIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) -lm

$(PLANNER_TEST): tests/planner_test.c src/planner.c src/planner.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) -Iinclude $(PROTOCOL_CFLAGS) $(PIN_CFLAGS) -Isrc $(CFLAGS) -Werror -o $@ tests/planner_test.c src/planner.c $(PIN_LIBS)

# the core placement (src/placement.c, docs/placement.md), on its own: the cpu lists and the audio and reserved cores of
# a mask
test-placement: $(PLACEMENT_TEST)
	./$(PLACEMENT_TEST)

$(PLACEMENT_TEST): tests/placement_test.c src/placement.c src/placement.h
	$(CC) -Isrc $(CFLAGS) -Werror -o $@ tests/placement_test.c src/placement.c $(PIN_LIBS)

# the transforms the format tables name (src/transforms.c, docs/formats.md): every one and its inverse over its vectors,
# and a lookup that is not one to one refused
test-transforms: $(TRANSFORMS_TEST)
	./$(TRANSFORMS_TEST)

$(TRANSFORMS_TEST): tests/transforms_test.c src/transforms.c src/transforms.h
	$(CC) -Isrc $(CONTRACT_CFLAGS) $(CFLAGS) -Werror -o $@ tests/transforms_test.c src/transforms.c $(PIN_LIBS) -lm

# src/relay.c when memory runs out: built here with its realloc calls renamed, so the test picks the one that fails
test-relay: $(RELAY_TEST)
	./$(RELAY_TEST)

$(RELAY_TEST): tests/relay_test.c src/relay.c src/relay.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) -Iinclude $(PROTOCOL_CFLAGS) $(CFLAGS) -Werror -Drealloc=relay_test_realloc -c -o tests/relay-test-relay.o src/relay.c
	$(CC) -Isrc $(CFLAGS) -Werror -o $@ tests/relay_test.c tests/relay-test-relay.o -pthread $(PIN_LIBS)
# the whole daemon when memory runs out: built with every allocation of its own sources going through tests/alloc_fail.c,
# and the scenario of tests/alloc_sweep.py run with each allocation refused in turn
ALLOC_SWEEP_DAEMON = tests/plugin-hostd-alloc-fail
$(ALLOC_SWEEP_DAEMON): $(TEST_CONTRACT_TREE) $(SRC) tests/alloc_fail.c tests/alloc_fail.h $(wildcard src/*.h) $(PROTOCOL_HEADERS) $(RENDERED) $(REPLY_WORDS) $(PROTOCOL_LIB)
	mkdir -p tests/alloc-fail-objs
	for f in $(SRC); do $(CC) $(CFLAGS) $(INCS) $(CONTRACT_CFLAGS) -DOMX_CONTRACTDIR='"$(TEST_CONTRACT_TREE)"' -DOMX_QUALIFICATION_TEST_STORE -include tests/alloc_fail.h -c -o tests/alloc-fail-objs/$$(basename $$f .c).o $$f || exit 1; done
	$(CC) $(CFLAGS) -c -o tests/alloc-fail-objs/alloc_fail.o tests/alloc_fail.c
	$(CC) tests/alloc-fail-objs/*.o $(PROTOCOL_LIBS) $(LDFLAGS) -pthread $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) -lm -o $@

# a refused plan over a longer one: the daemon's joint world cannot be built, and a pointer array ends against a guard page
PLAN_REFUSED_DAEMON = tests/plugin-hostd-plan-refused
$(PLAN_REFUSED_DAEMON): $(TEST_CONTRACT_TREE) $(SRC) tests/world_refuse.c tests/guard_calloc.c tests/guard_calloc.h $(wildcard src/*.h) $(PROTOCOL_HEADERS) $(RENDERED) $(REPLY_WORDS) $(PROTOCOL_LIB)
	mkdir -p tests/plan-refused-objs
	for f in $(SRC); do $(CC) $(CFLAGS) $(INCS) $(CONTRACT_CFLAGS) -DOMX_CONTRACTDIR='"$(TEST_CONTRACT_TREE)"' -DOMX_QUALIFICATION_TEST_STORE -include tests/guard_calloc.h -c -o tests/plan-refused-objs/$$(basename $$f .c).o $$f || exit 1; done
	$(CC) $(CFLAGS) -c -o tests/plan-refused-objs/guard_calloc.o tests/guard_calloc.c
	$(CC) $(CFLAGS) -c -o tests/plan-refused-objs/world_refuse.o tests/world_refuse.c
	$(CC) tests/plan-refused-objs/*.o $(PROTOCOL_LIBS) $(LDFLAGS) -pthread $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) -lm -ldl -o $@

.PHONY: test-plan-refused
test-plan-refused: $(PLAN_REFUSED_DAEMON) $(FAKE)
	PLUGIN_HOSTD_WORLD_REFUSE=1 ONLY=a_refused_plan_shorter_than_the_one_before_it_keeps_every_segment \
	  PLUGIN_HOSTD=./$(PLAN_REFUSED_DAEMON) FAKE_HOST=./$(FAKE) python3 tests/daemon_test.py > tests/plan-refused.out 2>&1 || { cat tests/plan-refused.out; exit 1; }
	grep -q '^ok   a_refused_plan_shorter_than_the_one_before_it_keeps_every_segment' tests/plan-refused.out

.PHONY: test-alloc-sweep
test-alloc-sweep: $(ALLOC_SWEEP_DAEMON) $(FAKE)
	ALLOC_SWEEP_DAEMON=./$(ALLOC_SWEEP_DAEMON) FAKE_HOST=./$(FAKE) python3 tests/alloc_sweep.py
	FAKE_HOST=./$(FAKE) python3 tests/alloc_sweep_sabotage.py "$(CC)" "$(CFLAGS) $(INCS) $(CONTRACT_CFLAGS)" "$(PROTOCOL_LIBS) $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS) $(LDFLAGS)" tests/alloc-fail-objs

# the relay's gesture table, lv2.c's refusal and pick tables, and the verbs' copies and answer when memory runs out:
# each is built with its allocation calls renamed, so the test picks the one that fails
test-alloc: $(GESTURE_ALLOC_TEST) $(LV2_ALLOC_TEST) $(VERBS_ALLOC_TEST)
	./$(GESTURE_ALLOC_TEST)
	./$(LV2_ALLOC_TEST)
	./$(VERBS_ALLOC_TEST)

$(GESTURE_ALLOC_TEST): tests/gesture_alloc_test.c src/relay.c src/relay.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) -Iinclude $(PROTOCOL_CFLAGS) $(PIN_CFLAGS) -Isrc $(CFLAGS) -Werror -Drealloc=alloc_test_realloc -o $@ tests/gesture_alloc_test.c -pthread $(PIN_LIBS)

$(LV2_ALLOC_TEST): tests/lv2_alloc_test.c src/lv2.c src/formats.h
	$(CC) $(INCS) -Isrc $(CFLAGS) -Werror -Drealloc=alloc_test_realloc -c -o tests/lv2-alloc-lv2.o src/lv2.c
	$(CC) $(INCS) -Isrc $(CFLAGS) -Werror -o $@ tests/lv2_alloc_test.c tests/lv2-alloc-lv2.o $(PIN_LIBS)

$(VERBS_ALLOC_TEST): tests/verbs_alloc_test.c src/verbs.c src/verbs.h $(FORMAT_OBJ) $(PROTOCOL_LIB)
	$(CC) $(INCS) -Isrc $(CFLAGS) -Werror -Dstrndup=alloc_test_strndup -Dstrdup=alloc_test_strdup \
	  -Dfree=alloc_test_free -o $@ tests/verbs_alloc_test.c $(FORMAT_OBJ) $(PROTOCOL_LIBS) -pthread -lm $(PIN_LIBS) $(DOMAIN_LIBS) $(PQDB_LIBS) $(CJSON_LIBS)

tests/stress.clap: tests/stress_plugin.c
	$(CC) $(CLAP_CFLAGS) $(CFLAGS) -Werror -shared -o $@ $<

# every guard broken on purpose, one at a time: its test must go red
sabotage: $(PROG_TEST) $(FAKE) tests/probe-child tests/stress.clap tests/lv2-probe-child tests/rt_interpose.so $(LV2_FIXTURE)
	PROTOCOL_DIR=$(PROTOCOL_DIR) FAKE_HOST=./$(FAKE) python3 tests/sabotage.py

# the jack server the real-worker tests run over: pipewire's own jack implementation (default) or JACK2's jackd
JACK_SERVER ?= pipewire

# the real workers over jack in a PipeWire of its own: omx-clap-host (OMX_CLAP_HOST) and, when MOD_HOST is
# given, mod-host with an LV2 bundle (LV2_DIR, LV2_URI, LV2_BUNDLE, LV2_PARAM name the plugin); with omx-clap-host's
# meter fixtures (FAKE_COMPRESSOR_CLAP, JACK_METER_SOURCE) the meters reach the controller through the daemon
# the reply curve_points must give, from omx-dsp's omx_curve_points (header only): the real instances' curves are held
# to it in tests/jack_e2e.py
OMXDSP_TEST_CFLAGS = $(shell $(PKG_CONFIG) --cflags 'omxdsp >= $(shell tools/dep-floor.sh omx-dsp-devel)' 2>/dev/null)
tests/curve_reply: tests/curve_reply.c
	@test -n "$(OMXDSP_TEST_CFLAGS)" || { echo "tests/curve_reply needs omx-dsp-devel (the floor of packaging/deps.txt)" >&2; exit 1; }
	$(CC) -std=gnu99 -Wall -Wextra -Werror -O2 $(OMXDSP_TEST_CFLAGS) -o $@ $< -lm

test-jack: $(PROG_TEST) tests/stress.clap tests/jack_levels tests/host_scenarios tests/curve_reply
	CURVE_REPLY=$(abspath tests/curve_reply) \
	JACK_SERVER=$(JACK_SERVER) PLUGIN_HOSTD=./$(PROG_TEST) STRESS_CLAP=$(abspath tests/stress.clap) JACK_LEVELS=$(abspath tests/jack_levels) \
	HOST_SCENARIOS=$(abspath tests/host_scenarios) SCENARIOS=$(abspath $(PROTOCOL_SCENARIOS)) ./tests/jack_e2e.sh

# a preset an instance saved loads back after a factory patch of Surge XT (#27), through the daemon and a real
# omx-clap-host (OMX_CLAP_HOST, default the installed one) over jack in a PipeWire of its own. Surge XT is the
# distribution's (clap-surge-xt and surge-xt on Fedora): a Surge XT that is not installed stops the run, never a skip.
# The patch names its macros ("Sync"), so loading it renames the plugin's parameters: a patch whose macros are all
# unnamed (Attacky's) renames nothing and the test could not see #27. SURGE_CLAP and SURGE_FACTORY_PATCH name another
# install's files.
SURGE_CLAP ?= /usr/lib64/clap/Surge_XT.clap
SURGE_FACTORY_PATCH ?= /usr/share/surge-xt/patches_factory/Basses/Squared.fxp
OMX_CLAP_HOST ?= $(shell command -v omx-clap-host)

.PHONY: test-preset-identity
test-preset-identity: $(PROG_TEST) plugin-hostd-probe tests/stress.clap tests/jack_levels
	@for f in "$(SURGE_CLAP)" "$(SURGE_FACTORY_PATCH)" "$(OMX_CLAP_HOST)"; do \
	    [ -e "$$f" ] || { echo "test-preset-identity: missing '$$f' (Surge XT: clap-surge-xt and surge-xt; omx-clap-host)" >&2; exit 2; }; \
	done
	JACK_E2E_PY=preset_identity_e2e.py JACK_SERVER=$(JACK_SERVER) PLUGIN_HOSTD=$(abspath $(PROG_TEST)) OMX_CLAP_HOST=$(OMX_CLAP_HOST) \
	SURGE_CLAP=$(SURGE_CLAP) SURGE_FACTORY_PATCH=$(SURGE_FACTORY_PATCH) PATH=$(abspath .):$$PATH \
	STRESS_CLAP=$(abspath tests/stress.clap) JACK_LEVELS=$(abspath tests/jack_levels) ./tests/jack_e2e.sh

# test-jack against JACK2's jackd (the server Zynthian runs) instead of pipewire's own jack implementation
test-jack2:
	$(MAKE) test-jack JACK_SERVER=jackd

# the LV2 adapter of a real omx-clap-host behind the daemon, with the real mod-host (MOD_HOST, default the one on PATH),
# over jack in a PipeWire of its own: omx-clap-host and its fixture bundles are built in an omx-clap-core checkout
# (OMX_CLAP_HOST_SRC) against this tree's headers; without OMX_CLAP_HOST_SRC the target says it skipped
OMX_CLAP_HOST_SRC ?=
LV2_FIXTURE = tests/plugin-hostd-fixture.lv2/plugin-hostd-fixture.so

test-lv2-adapter:
	@if [ -z "$(OMX_CLAP_HOST_SRC)" ]; then \
	    echo "skip test-lv2-adapter: OMX_CLAP_HOST_SRC is not set (an omx-clap-core checkout to build omx-clap-host from)"; \
	else \
	    $(MAKE) lv2-adapter-e2e; \
	fi

lv2-adapter-e2e: $(PROG_TEST) tests/stress.clap tests/jack_levels $(LV2_FIXTURE)
	@set -e; src=$$(cd $(OMX_CLAP_HOST_SRC) && pwd); \
	$(MAKE) -C $$src PLUGIN_HOSTD_DIR=$(abspath .) omx-clap-host build/lv2/omx-host-fixture.lv2/omx-host-fixture.so; \
	JACK_E2E_PY=lv2_adapter_e2e.py JACK_SERVER=pipewire PLUGIN_HOSTD=./$(PROG_TEST) OMX_CLAP_HOST=$$src/omx-clap-host \
	ADAPTER_BUNDLES=$$src/build/lv2 LV2_FIXTURE=$(abspath tests) MOD_HOST=$${MOD_HOST:-$$(command -v mod-host)} \
	STRESS_CLAP=$(abspath tests/stress.clap) JACK_LEVELS=$(abspath tests/jack_levels) ./tests/jack_e2e.sh

$(LV2_FIXTURE): tests/lv2_fixture.c
	$(CC) $(shell $(PKG_CONFIG) --cflags lv2) $(CFLAGS) -Werror -shared -o $@ $<

# the protocol's scenario corpus, the runner every host is tested with
tests/host_scenarios: $(PROTOCOL_RUNNER) $(PROTOCOL_LIB)
	$(CC) $(INCS) $(CFLAGS) -Werror -o $@ $< $(PROTOCOL_LIBS) -lpthread $(PIN_LIBS)

tests/jack_levels: tests/jack_levels.c
	$(CC) $(shell $(PKG_CONFIG) --cflags jack) $(CFLAGS) -Werror -o $@ $< $(shell $(PKG_CONFIG) --libs jack) $(PIN_LIBS) -lm

# what <plugin-hostd/protocol.h> (plugin-hostd-protocol's) declares, written out in this tree's pages: docs/guide.md and the
# man page between their markers, and the probe output's schema. The JSON of the protocol and mod-host's are
# plugin-hostd-protocol's (PROTOCOL_JSON, MODHOST_JSON)
GEN = tools/protocol-gen
GENERATED = docs/guide.md doc/plugin-hostd.1 protocol/probe-output.schema.json

$(GEN): tools/protocol-gen.c src/domain_words.c src/domain_words.h src/machine.h src/probe_words.h src/qualification_words.c src/qualification_words.h $(PROTOCOL_HEADERS) $(RENDERED)
	$(CC) -Wall -Wextra -Werror -std=gnu99 -Iinclude -Isrc $(PROTOCOL_CFLAGS) $(CONTRACT_CFLAGS) $(DOMAIN_CFLAGS) -o $@ tools/protocol-gen.c src/domain_words.c src/qualification_words.c $(PIN_LIBS) $(DOMAIN_LIBS)

gen: $(GEN)
	$(GEN) probe-schema protocol/probe-output.schema.in > protocol/probe-output.schema.json.new && mv protocol/probe-output.schema.json.new protocol/probe-output.schema.json
	for f in docs/guide.md doc/plugin-hostd.1; do $(GEN) splice $$f > $$f.new && mv $$f.new $$f || exit 1; done

# fails on any drift: every generated output must be byte-identical to a fresh generation, every region the generator
# knows must be in a file. They are written against the protocol floor (tools/protocol-floor.sh): against a newer
# installed minor, which may add rows, they are not compared and the check says so; GENERATED_COMPARE=always compares
# them against whatever is installed (tests/perturbation.py, after make gen)
GENERATED_COMPARE ?= floor
check-generated: $(GEN)
	@floor=$$(sh tools/protocol-floor.sh); installed=$$($(PKG_CONFIG) --modversion plugin-hostd-protocol 2>/dev/null); \
	if [ "$(GENERATED_COMPARE)" != always ] && [ "$$installed" != "$$floor" ]; then \
	  echo "generated files are written against plugin-hostd-protocol $$floor; $$installed is installed: not compared"; exit 0; fi; \
	set -e; tmp=$$(mktemp -d); trap 'rm -rf $$tmp' EXIT; \
	$(GEN) probe-schema protocol/probe-output.schema.in > $$tmp/probe; cmp $$tmp/probe protocol/probe-output.schema.json; \
	for f in docs/guide.md doc/plugin-hostd.1; do $(GEN) splice $$f > $$tmp/out; cmp $$tmp/out $$f; done; \
	$(GEN) regions > $$tmp/regions; test -s $$tmp/regions; \
	while read r; do grep -q "BEGIN GENERATED protocol:$$r\( .*\)\?$$" docs/guide.md doc/plugin-hostd.1 || { echo "region $$r is in no file"; exit 1; }; done < $$tmp/regions; \
	echo "generated files are current"

# the README and the guide sell the packages: no build command on them, and BUILDING.md carries the build
check-readme:
	python3 tests/readme_build.py

# the prose beside the generated protocol tables: still the daemon's and its workers' verified behavior today
check-readme-facts:
	python3 tests/readme_facts.py

# the own-host page: its commands are few, and the reader that CI runs them with stops on any wrong reply
check-own-host-page:
	python3 tests/own_host_page.py selftest

# no pin: a dependency is declared in the spec and debian/control with a floor (no ceiling), nowhere else
check-no-pins:
	python3 tests/no_pins.py

# the packaged daemon carries no test seam for the qualification store: the binary built here is the one the packages hold;
# BIN names an installed one instead
BIN ?= $(PROG)
.PHONY: check-no-test-seam
check-no-test-seam: $(BIN)
	python3 tests/no_test_seam.py $(BIN)

# the package that ships contract.d/<major>/plugin-hostd requires omx-contract 3.2.0 or later at run time, in the spec and
# debian/control: the first whose schema takes every row key of the tables (#165)
# the dependency floors are declared once, in packaging/deps.txt (floors only); the engine is Open-Mixer/.github's
# deps-render (CI runs it as that action): locally name a checkout of it, make deps-check DOTGITHUB=<dir>;
# make deps writes the floors into the spec and debian/control
DOTGITHUB ?=
.PHONY: deps deps-check
deps:
	@test -n "$(DOTGITHUB)" || { echo "$@: name a checkout of Open-Mixer/.github: make $@ DOTGITHUB=<dir>" >&2; exit 2; }
	$(DOTGITHUB)/.github/actions/deps-render/render.sh --write .
deps-check:
	@test -n "$(DOTGITHUB)" || { echo "$@: name a checkout of Open-Mixer/.github: make $@ DOTGITHUB=<dir>" >&2; exit 2; }
	$(DOTGITHUB)/.github/actions/deps-render/render.sh --check .

check-contract-floor:
	python3 tests/contract_floor.py

# every dependency deps.txt lists is declared at its floor and no ceiling, in the spec and in debian/control (tests/floors_only.py)
check-floors-only:
	python3 tests/floors_only.py

# plugin-hostd builds neither package that moved out: plugin-hostd-full is Open-Mixer/plugin-hostd-full's (#84), the
# Python codec python3-plugin-hostd-protocol is plugin-hostd-protocol's, a floor with no epoch (tests/no_moved_packages.py)
check-no-moved-packages:
	python3 tests/no_moved_packages.py

# the plugin-hostd-protocol floor is one number, at or above the first protocol release that declares what the sources
# use (tests/protocol_floor.py)
test: check-protocol-floor
check-protocol-floor:
	python3 tests/protocol_floor.py
	python3 tests/pin_words_floor.py

# a workflow step the runner may be unable to run fails where it cannot run it (#107)
# the org.openmixer.preset file (docs/presets.md) holds to protocol/preset.schema.json, and a broken one does not
check-preset-schema:
	python3 tests/preset_format.py

# make install into a scratch DESTDIR carries both schemas the development package ships (#145); the protocol's is
# plugin-hostd-protocol's
test-install-schemas: all
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf $$tmp' EXIT; \
	$(MAKE) --no-print-directory install DESTDIR=$$tmp PREFIX=/usr >/dev/null; \
	for f in probe-output.schema.json preset.schema.json; do \
	  test -s $$tmp/usr/share/plugin-hostd/$$f || { echo "not installed: usr/share/plugin-hostd/$$f"; exit 1; }; \
	done; \
	echo "install carries the two schemas"

# the C documentation gate is doxygen (tools/Doxyfile over the headers): a warning that tools/doxygen.baseline does not
# list fails, and so does a listed one that is gone; the baseline only shrinks. Needs doxygen.
.PHONY: check-doxygen
check-doxygen:
	sh tools/doxygen_gate.sh

# ruff's own ratchet on the Python client of the tests: D and the default rules (ruff.toml), today's findings carried by `# noqa`
# comments, so a new one is a plain ruff failure and fixing one deletes its noqa. Needs ruff.
.PHONY: check-ruff
check-ruff:
	ruff check tests/lib/plugin_hostd_client.py

# the two gates only shrink, by mechanism (tools/doc_shrink.sh against the base branch: DOC_GATE_BASE, origin/main by
# default); tests/doc_gate_test.sh proves it, and that doxygen_gate.sh --update only lowers the baseline
.PHONY: check-doc-shrink test-doc-gates
check-doc-shrink:
	sh tools/doc_shrink.sh
test-doc-gates:
	sh tests/doc_gate_test.sh

check-ci-guards:
	python3 tests/ci_guards.py

# the probe output's words shared with omx-contract are the contract's: each enum the template takes from it matches the
# installed omx-vocabulary.schema.json, and the template types none of the contract's lists by hand
test-vocabulary:
	python3 tests/vocabulary_derived.py

# the qualification words are this tree's domain (contract.d/qualification), read by the probe through the C loader: no render of it here, the
# probe's words follow a changed copy, an absent or too old domain is refused by name
test-qualification-domain: $(PROBE) tests/probe-child tests/stress.clap
	PROBE=./$(PROBE) python3 tests/qualification_domain.py

# the domain is plugin-hostd's: its document and catalogs hold the golden words and install as the loader reads them
.PHONY: test-qualification-domain-owned
test-qualification-domain-owned:
	python3 tests/qualification_domain_owned.py

# QUALIFICATION_PIN_VERDICTS names plugin-hostd-protocol's pin verdict words (its domain pin), it holds no list (V12)
.PHONY: test-qualification-pin-from
test-qualification-pin-from:
	OMX_CONTRACT='$(OMX_CONTRACT)' python3 tests/qualification_pin_from.py

# the probe runner over the stress plugin: crash, hang and a process left behind each give the named outcome in a document
# that validates
test-probe: $(PROBE) $(PROBE_LOCK) tests/probe-child tests/stress.clap tests/lv2-probe-child tests/rt_interpose.so tests/sched-refuse.so $(LV2_FIXTURE)
	python3 tests/probe_test.py

# lv2_measure's arguments and lines, with no lilv and no interposer: the LV2 tests of the runner load the fixture with it
tests/lv2-probe-child: tests/lv2_probe_child.c
	$(CC) -Iinclude $(PROTOCOL_CFLAGS) $(PIN_CFLAGS) $(shell $(PKG_CONFIG) --cflags lv2) $(CFLAGS) -Wall -Wextra -Werror -o $@ $< -ldl $(PIN_LIBS)

tests/rt_interpose.so: tests/rt_interpose_stub.c
	$(CC) $(CFLAGS) -Werror -shared -o $@ $<

# a sched_setscheduler that refuses, preloaded into the runner: the record says the kernel refused, never the grant
tests/sched-refuse.so: tests/sched_refuse.c
	$(CC) $(CFLAGS) -Werror -shared -o $@ $<

tests/probe-child: tests/probe_child.c
	$(CC) $(CLAP_CFLAGS) $(CFLAGS) -Wall -Wextra -Werror -o $@ $< -ldl $(PIN_LIBS)

# describe over the recorded field dumps (tests/fixtures/fields/, docs/formats.md#the-field-dump): each gives its recorded
# descriptor, which validates; each refusal names what it refuses; a stand-in child gives the same descriptor
test-describe: $(PROBE)
	PROBE=./$(PROBE) python3 tests/describe_test.py
	PROBE=./$(PROBE) python3 tests/describe_scopes_test.py
	PROBE=./$(PROBE) python3 tests/describe_clap_meters_test.py
	PROBE=./$(PROBE) python3 tests/describe_twin_test.py

# describe --pages (docs/formats.md#the-pages-describe-pages-writes): a group's controls one page per 8, in declared
# order; several hundred ungrouped parameters still get pages, the same on every run
test-describe-pages: $(PROBE)
	PROBE=./$(PROBE) python3 tests/describe_pages_test.py

# what is omx-contract's is read from it: the runner's default rates, the protocol's parameter scales and the probe
# schema's latency methods follow a scratch copy of its headers with other values
test-contract: $(PROBE)
	PARAM_CONTRACT_PATH='$(CURDIR)/tests/fixtures/contract.d' PROBE=./$(PROBE) CJSON_CFLAGS='$(CJSON_CFLAGS)' CJSON_LIBS='$(CJSON_LIBS)' python3 tests/contract_derived.py

# the probe output: its three fixtures validate and five broken copies of the first are refused
test-probe-schema:
	python3 tests/probe_schema.py

# the declaration is the one copy: change values in a scratch copy of it, regenerate, rebuild, and the daemon and the docs follow
test-perturbation: $(PROG_TEST) $(FAKE) $(GEN)
	PROTOCOL_DIR=$(PROTOCOL_DIR) FAKE_HOST=./$(FAKE) python3 tests/perturbation.py

# a consumer compiles against the installed header alone, through pkg-config, as plain C
# each step names itself when it fails; pkg-config prints its own reason (an unmet Requires: of plugin-hostd.pc)
test-consumer:
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf $$tmp' EXIT; \
	$(MAKE) -s install_protocol PREFIX=$$tmp DESTDIR= \
	  || { echo "FAIL test-consumer: make install_protocol into a scratch prefix"; exit 1; }; \
	export PKG_CONFIG_PATH=$$tmp/share/pkgconfig$${PKG_CONFIG_PATH:+:$$PKG_CONFIG_PATH}; \
	$(PKG_CONFIG) --print-errors --exists plugin-hostd \
	  || { echo "FAIL test-consumer: pkg-config --exists plugin-hostd: the installed plugin-hostd.pc's Requires: are not met (pkg-config's reason above)"; exit 1; }; \
	$(CC) $$($(PKG_CONFIG) --cflags plugin-hostd) -std=c99 -Wall -Wextra -Werror \
	  -o $$tmp/consumer tests/consumer.c $$($(PKG_CONFIG) --libs plugin-hostd) \
	  || { echo "FAIL test-consumer: tests/consumer.c against the installed headers and library"; exit 1; }; \
	$$tmp/consumer || { echo "FAIL test-consumer: the consumer built against the installed package"; exit 1; }

# test-consumer's own failure names its step and pkg-config's reason (tests/consumer_errors_test.sh)
test-consumer-errors:
	MAKE="$(MAKE)" sh tests/consumer_errors_test.sh

# --pin-files: the files a pin holds as an add collects them, the list plugin-qualify takes (plugin-qualify#228)
test-pin-files: $(PROG_TEST)
	sh tests/pin_files_test.sh ./$(PROG_TEST)

# which bundle an LV2 uri is when several name it: plugin-db's declared rule, newest version then search path and byte
# order (#57)
test-bundle-rule: $(PROG_TEST) $(SCANDIR_LISTING)
	sh tests/bundle_rule_test.sh ./$(PROG_TEST) ./$(SCANDIR_LISTING)

# --search-path: the LV2 and CLAP directories the daemon searches and their sources, the lists plugin-qualify scans
# (plugin-qualify#9)
test-search-path: $(PROG_TEST)
	sh tests/search_path_test.sh ./$(PROG_TEST)
