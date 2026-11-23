/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * The cost the daemon reads from the qualification store (src/qualcost.c, through libplugin-qualification-db), against
 * store fixtures built from that library's own schema (tests/qual_fixture.py): the figure of the right rate and
 * quantum, the larger of two records, the cell the estimate verb reads, the memory; a record file of the old
 * qualification_dir is read by nothing; and a store that cannot be opened is refused by its qualification-db.* code.
 * tests/sabotage.py breaks one rule at a time.
 *
 * Usage: qualcost-test [<test name>]
 * Compiled with -DQUAL_SCHEMA='"<schema/qualification.sql>"', -DQUAL_FIXTURE='"tests/qual_fixture.py"',
 * -DQUALCOST_SOURCE='"src/qualcost.c"' and -DTEST_CONTRACT_TREE='"<the installed machine domain>"'.
 */

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include <plugin-qualification-db/pqdb.h>

#include "qualcost.h"

static int g_failed;
static char g_dir[256];
static pqdb *g_db;

#define CHECK(cond, ...) \
    do { \
        if (!(cond)) \
        { \
            fprintf(stderr, "FAIL %s:%d: ", __func__, __LINE__); \
            fprintf(stderr, __VA_ARGS__); \
            fprintf(stderr, "\n"); \
            g_failed = 1; \
            return; \
        } \
    } while (0)

/* the fixture <g_dir>/<name>.sqlite from the cells, a space-separated list of qual_fixture.py's arguments */
static void fixture(const char *name, const char *args)
{
    char cmd[2048];

    snprintf(cmd, sizeof(cmd), "python3 %s %s %s/%s.sqlite %s", QUAL_FIXTURE, QUAL_SCHEMA, g_dir, name, args);
    if (system(cmd) != 0)
    {
        fprintf(stderr, "the fixture %s was not built: %s\n", name, cmd);
        exit(2);
    }
}

/* opens <g_dir>/<name>.sqlite as the base, no user layer; 0, or what pqdb_open_at answers, its error in *err */
static int open_fixture(const char *name, pqdb **db, pqdb_error *err)
{
    char path[512];

    snprintf(path, sizeof(path), "%s/%s.sqlite", g_dir, name);
    return pqdb_open_at(path, NULL, TEST_CONTRACT_TREE, db, err);
}

static void refused_as(const char *name, const char *code)
{
    pqdb *db = NULL;
    pqdb_error err;
    char why[512];
    int status = open_fixture(name, &db, &err);

    if (status == 0)
    {
        pqdb_close(db);
        CHECK(0, "%s opened, and the store is to be refused as %s", name, code);
    }
    qualcost_refusal(status, &err, why, sizeof(why));
    CHECK(!strncmp(why, code, strlen(code)) && why[strlen(code)] == ':', "%s: refused as '%s', not %s", name, why, code);
    CHECK(strstr(why, name) != NULL, "%s: the refusal names the file: '%s'", name, why);
}

/* a verdict's figures: the cost of the right rate and quantum, as a fraction of a core */
static void the_figure_is_the_p95_at_the_rate_and_quantum_as_a_fraction_of_a_core(void)
{
    double c = qualcost_read(g_db, "org.example.a", 48000, 128);

    CHECK(fabs(c - 0.24) < 1e-12, "5000 ns per sample at 48 kHz is 0.24 of a core, not %g", c);
    c = qualcost_read(g_db, "org.example.a", 96000, 64);
    CHECK(fabs(c - 96000.0 / 1e9) < 1e-12, "the other grid point of the record is its own figure: %g", c);
}

static void a_rate_or_quantum_the_store_lacks_is_unknown(void)
{
    CHECK(qualcost_read(g_db, "org.example.a", 44100, 128) == -1.0, "no such rate");
    CHECK(qualcost_read(g_db, "org.example.a", 48000, 256) == -1.0, "no such quantum");
}

static void the_larger_of_two_records_of_one_plugin_stands(void)
{
    double c = qualcost_read(g_db, "org.example.b", 48000, 128);

    CHECK(fabs(c - 0.48) < 1e-12, "10000 ns of one binary beats 2000 ns of the other: %g", c);
}

static void a_plugin_the_store_does_not_name_has_no_figure(void)
{
    CHECK(qualcost_read(g_db, "org.example.nobody", 48000, 128) == -1.0, "no such plugin");
    CHECK(qualcost_read(g_db, NULL, 48000, 128) == -1.0, "no name");
    CHECK(qualcost_read(NULL, "org.example.a", 48000, 128) == -1.0, "no store");
}

static void the_cell_is_the_median_and_the_measured_latency(void)
{
    qualcost_cell_t c;

    CHECK(qualcost_cell(g_db, "org.example.e", 48000, 128, &c) == QUALCOST_CELL_FOUND, "e has the cell");
    CHECK(c.median_ns == 3000 && c.latency_frames == 70, "the median and the measured frames: %g %g", c.median_ns,
          c.latency_frames);
}

static void a_cell_without_a_measured_latency_takes_the_declared_one(void)
{
    qualcost_cell_t c;

    CHECK(qualcost_cell(g_db, "org.example.f", 48000, 128, &c) == QUALCOST_CELL_FOUND, "f has the cell");
    CHECK(c.latency_frames == 32, "the declared frames: %g", c.latency_frames);
}

static void a_point_without_a_latency_or_at_another_rate_is_no_cell(void)
{
    qualcost_cell_t c;

    CHECK(qualcost_cell(g_db, "org.example.g", 48000, 128, &c) == QUALCOST_CELL_NO_POINT, "g has a cost, no latency");
    CHECK(qualcost_cell(g_db, "org.example.a", 48000, 128, &c) == QUALCOST_CELL_NO_POINT, "a has no latency");
    CHECK(qualcost_cell(g_db, "org.example.e", 44100, 128, &c) == QUALCOST_CELL_NO_POINT, "no such rate");
    CHECK(qualcost_cell(g_db, "org.example.e", 48000, 256, &c) == QUALCOST_CELL_NO_POINT, "no such quantum");
}

static void a_plugin_no_record_names_has_no_record(void)
{
    qualcost_cell_t c;

    CHECK(qualcost_cell(g_db, "org.example.nobody", 48000, 128, &c) == QUALCOST_CELL_NO_RECORD, "no such plugin");
}

static void the_larger_of_each_figure_of_two_records_stands(void)
{
    qualcost_cell_t c;
    qualcost_memory_t m;

    CHECK(qualcost_cell(g_db, "org.example.h", 48000, 128, &c) == QUALCOST_CELL_FOUND, "h has the cell");
    CHECK(c.median_ns == 2000 && c.latency_frames == 10, "2000 ns of one record, 10 frames of the other: %g %g",
          c.median_ns, c.latency_frames);
    CHECK(qualcost_memory(g_db, "org.example.h", 48000, 128, &m) == 0, "h has memory");
    CHECK(m.first_kb == 100 && m.per_instance_kb == 9, "100 KB first of one record, 9 KB per instance of the other: %g %g",
          m.first_kb, m.per_instance_kb);
}

static void the_memory_is_the_first_instance_and_each_one_more(void)
{
    qualcost_memory_t m;

    CHECK(qualcost_memory(g_db, "org.example.e", 48000, 128, &m) == 0, "e has memory");
    CHECK(m.first_kb == 100 && m.per_instance_kb == 10, "firstInstanceKb and perInstanceKb: %g %g", m.first_kb,
          m.per_instance_kb);
}

static void no_memory_figure_is_unknown_and_never_zero(void)
{
    qualcost_memory_t m;

    CHECK(qualcost_memory(g_db, "org.example.a", 48000, 128, &m) == -1, "a holds no memory");
    CHECK(qualcost_memory(g_db, "org.example.e", 44100, 128, &m) == -1, "no such rate");
    CHECK(qualcost_memory(g_db, "org.example.nobody", 48000, 128, &m) == -1, "no such plugin");
}

/* LV2 URIs reach the daemon percent-encoded as often as not; the store holds the URI as plugin-qualify wrote it */
static void a_percent_encoded_iri_finds_the_record_of_its_decoded_spelling(void)
{
    CHECK(fabs(qualcost_read(g_db, "urn:a%20b", 48000, 128) - 0.24) < 1e-12, "encoded id, decoded record");
    CHECK(fabs(qualcost_read(g_db, "urn:a b", 48000, 128) - 0.24) < 1e-12, "the decoded spelling itself");
    CHECK(fabs(qualcost_read(g_db, "urn:a%20c", 48000, 128) - 0.24) < 1e-12, "a record that holds the encoded spelling");
    CHECK(qualcost_read(g_db, "urn:a%2", 48000, 128) == -1.0, "a stray percent is no escape");
}

/* the old directory of record files is read by nothing: a record file there, beside the store, names a plugin the
 * store does not, and that plugin has no figure */
static void a_record_file_of_the_old_qualification_dir_is_not_read(void)
{
    char path[512];
    qualcost_cell_t c;
    FILE *f;

    snprintf(path, sizeof(path), "%s/org.example.old@1.0-aaaaaaaaaaaa.default.qualification.json", g_dir);
    f = fopen(path, "w");
    CHECK(f != NULL, "the record file is written");
    fputs("{\"schema\":\"plugin-qualify.qualification-record/1\",\"plugin\":{\"format\":\"clap\",\"id\":\"org.example.old\"},"
          "\"measurements\":{\"grid\":[{\"rate\":48000,\"quantum\":128,\"outcome\":\"probe.ok\",\"latency\":"
          "{\"measuredFrames\":9},\"cost\":{\"median\":1,\"percentile\":{\"p\":95,\"value\":5000},\"blocks\":1,"
          "\"warmupBlocks\":0}}]}}", f);
    fclose(f);
    CHECK(qualcost_read(g_db, "org.example.old", 48000, 128) == -1.0, "the file's figure is read");
    CHECK(qualcost_cell(g_db, "org.example.old", 48000, 128, &c) == QUALCOST_CELL_NO_RECORD, "the file's cell is read");
}

static int source_holds(const char *needle)
{
    char text[1 << 16];
    FILE *f = fopen(QUALCOST_SOURCE, "r");
    size_t n;

    if (!f)
        exit(2);
    n = fread(text, 1, sizeof(text) - 1, f);
    fclose(f);
    text[n] = '\0';
    return strstr(text, needle) != NULL;
}

/* no dual read, no fallback (the qualification store spec, section 10): the reader names no directory of records, reads
 * no variable, and takes the one place pqdb_open gives it, never the test entry pqdb_open_at */
static void the_reader_names_no_record_directory_variable_or_test_entry(void)
{
    static const char *const banned[] = { "qualification.json", "qualification_dir", "OMX_QUALIFICATION_DIR", "opendir",
                                          "readdir", "getenv", "pqdb_open_at", "fopen", "memset", "pqdb_query q;", NULL };
    int k;

    for (k = 0; banned[k]; k++)
        CHECK(!source_holds(banned[k]), "src/qualcost.c names '%s'", banned[k]);
    CHECK(source_holds("pqdb_open("), "src/qualcost.c does not open the store through pqdb_open");
    /* a zeroed pqdb_query asks for rate 0 and quantum 0 and matches nothing: every query starts from PQDB_QUERY_ANY */
    CHECK(source_holds("pqdb_query q = PQDB_QUERY_ANY"), "src/qualcost.c does not start its query from PQDB_QUERY_ANY");
}

/* plugin-hostd takes the system scope run as root and the user's otherwise (the rule its qualification_dir had) */
static void the_scope_is_the_system_s_as_root_and_the_user_s_otherwise(void)
{
    CHECK(qualcost_scope() == (geteuid() == 0 ? PQDB_SCOPE_SYSTEM : PQDB_SCOPE_USER), "euid %d", (int)geteuid());
}

/* libplugin-qualification-db from 2026112001: only ENOENT is an absent base, and it opens as an empty layer (pqdb_base_absent),
 * so a console with no store yet reads no figure for any plugin rather than a refusal */
static void an_absent_store_opens_empty_and_gives_no_figure(void)
{
    pqdb *db = NULL;
    pqdb_error err;
    int status = open_fixture("nowhere", &db, &err);

    CHECK(status == 0, "nowhere: an absent base opens as an empty layer, status %d", status);
    if (status != 0)
        return;
    CHECK(pqdb_base_absent(db) == 1, "nowhere: the base is said absent");
    CHECK(qualcost_read(db, "org.example.a", 48000, 128) == -1.0, "nowhere: no figure for a plugin");
    pqdb_close(db);
}

static void a_store_of_another_schema_version_is_refused_as_schema_other(void)
{
    refused_as("version2", "qualification-db.schema-other");
}

static void a_file_that_is_no_store_is_refused_as_not_a_store(void)
{
    refused_as("version0", "qualification-db.not-a-store");
}

static void a_word_no_domain_item_holds_is_refused_as_word_unknown(void)
{
    refused_as("badword", "qualification-db.word-unknown");
}

static const struct { const char *name; void (*fn)(void); } g_tests[] = {
#define T(f) { #f, f }
    T(the_figure_is_the_p95_at_the_rate_and_quantum_as_a_fraction_of_a_core),
    T(a_rate_or_quantum_the_store_lacks_is_unknown),
    T(the_larger_of_two_records_of_one_plugin_stands),
    T(a_plugin_the_store_does_not_name_has_no_figure),
    T(the_cell_is_the_median_and_the_measured_latency),
    T(a_cell_without_a_measured_latency_takes_the_declared_one),
    T(a_point_without_a_latency_or_at_another_rate_is_no_cell),
    T(a_plugin_no_record_names_has_no_record),
    T(the_larger_of_each_figure_of_two_records_stands),
    T(the_memory_is_the_first_instance_and_each_one_more),
    T(no_memory_figure_is_unknown_and_never_zero),
    T(a_percent_encoded_iri_finds_the_record_of_its_decoded_spelling),
    T(a_record_file_of_the_old_qualification_dir_is_not_read),
    T(the_reader_names_no_record_directory_variable_or_test_entry),
    T(the_scope_is_the_system_s_as_root_and_the_user_s_otherwise),
    T(an_absent_store_opens_empty_and_gives_no_figure),
    T(a_store_of_another_schema_version_is_refused_as_schema_other),
    T(a_file_that_is_no_store_is_refused_as_not_a_store),
    T(a_word_no_domain_item_holds_is_refused_as_word_unknown),
#undef T
};

int main(int argc, char **argv)
{
    size_t n, ran = 0;
    int bad = 0;
    char cmd[300];
    pqdb_error err;
    char dir[] = "/tmp/qualcost-test.XXXXXX";

    if (!mkdtemp(dir))
        return 2;
    snprintf(g_dir, sizeof(g_dir), "%s", dir);
    /* cells: sha256 (a hex digit, 64 times), uri, rate, quantum, median, p95, declared, measured, firstKb, perKb */
    fixture("good",
            "a,org.example.a,48000,128,1000,5000,-,-,-,- a,org.example.a,96000,64,1,1,-,-,-,- "
            "b,org.example.b,48000,128,1,2000,-,-,-,- c,org.example.b,48000,128,1,10000,-,-,-,- "
            "e,org.example.e,48000,128,3000,6000,64,70,100,10 "
            "f,org.example.f,48000,128,1000,2000,32,-,-,- "
            "9,org.example.g,48000,128,1000,2000,-,-,-,- "
            "d,org.example.h,48000,128,1000,2000,0,10,100,5 f,org.example.h,48000,128,2000,3000,0,5,80,9 "
            "a,'urn:a b',48000,128,1000,5000,-,-,-,- "
            "b,urn:a%20c,48000,128,1000,5000,-,-,-,-");
    fixture("version2", "--user-version 2 a,org.example.a,48000,128,1000,5000,-,-,-,-");
    fixture("version0", "--user-version 0 a,org.example.a,48000,128,1000,5000,-,-,-,-");
    fixture("badword", "--bad-word a,org.example.a,48000,128,1000,5000,-,-,-,-");
    {
        char path[512];

        snprintf(path, sizeof(path), "%s/good.sqlite", g_dir);
        if (pqdb_open_at(path, NULL, TEST_CONTRACT_TREE, &g_db, &err) != 0)
        {
            fprintf(stderr, "the good fixture does not open: %s\n", err.message);
            return 2;
        }
    }
    for (n = 0; n < sizeof(g_tests) / sizeof(g_tests[0]); n++)
    {
        if (argc > 1 && strcmp(argv[1], g_tests[n].name))
            continue;
        g_failed = 0;
        g_tests[n].fn();
        ran++;
        if (g_failed)
            bad++;
        else
            printf("ok   %s\n", g_tests[n].name);
    }
    pqdb_close(g_db);
    snprintf(cmd, sizeof(cmd), "rm -rf %s", g_dir);
    if (system(cmd) != 0)
        bad++;
    if (!ran)
        return 2;
    printf("qualcost tests %s (%zu run, %d failed)\n", bad ? "FAILED" : "ok", ran, bad);
    return bad ? 1 : 0;
}
