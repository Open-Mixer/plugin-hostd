/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The search settings (#212): lv2_path defaults to Zynthian's own LV2_PATH and then the lib64 folders, $LV2_PATH stands
 * in for it, lv2_extra is searched after it, and $CLAP_PATH is searched before the CLAP default, not instead of it. */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <unistd.h>

#include "conf.h"

static int failures;

static void check(int ok, const char *what)
{
    if (!ok)
    {
        failures++;
        printf("FAIL conf: %s\n", what);
    }
}

/* the position of a directory in a list, -1 when it is not a whole entry of it */
static int where(const char *list, const char *dir)
{
    char copy[PATH_MAX * 2], *entry, *save = NULL;
    int k = 0;

    snprintf(copy, sizeof(copy), "%s", list);
    for (entry = strtok_r(copy, ":", &save); entry; entry = strtok_r(NULL, ":", &save), k++)
        if (!strcmp(entry, dir))
            return k;
    return -1;
}

/* list starts with the folders of head, a whole folder each: head is followed by the end of list or a ':' */
static int starts_with_dirs(const char *list, const char *head)
{
    const size_t n = strlen(head);

    return !strncmp(list, head, n) && (list[n] == '\0' || list[n] == ':');
}

int main(void)
{
    conf_t conf;
    static const char *const zynthian[] = { "/usr/lib/lv2", "/usr/lib/aarch64-linux-gnu/lv2", "/usr/local/lib/lv2",
                                            "/usr/local/lib/aarch64-linux-gnu/lv2" };
    int k, last = -1;

    unsetenv("LV2_PATH");
    unsetenv("CLAP_PATH");
    conf_defaults(&conf);
    for (k = 0; k < 4; k++)
    {
        int at = where(conf.lv2_path, zynthian[k]);

        check(at > last, zynthian[k]);
        last = at;
    }
    check(where(conf.lv2_path, "/usr/lib/arm-linux-gnueabihf/lv2") >= 0, "the 32-bit Pi multiarch folder");
    check(where(conf.lv2_path, "/usr/lib/x86_64-linux-gnu/lv2") >= 0, "the x86_64 multiarch folder");
    check(where(conf.lv2_path, "/usr/lib64/lv2") > where(conf.lv2_path, "/usr/local/lib/aarch64-linux-gnu/lv2"),
          "lib64 folders come after Zynthian's four");
    /* the default is the list plugin-hostd-protocol declares, never a copy of it here; it starts at ~/.clap, then
     * /usr/lib/clap */
    check(!strcmp(conf.clap_path, PHD_DEFAULT_CLAP_PATH), "clap_path defaults to the declared PHD_DEFAULT_CLAP_PATH");
    check(starts_with_dirs(conf.clap_path, "~/.clap:/usr/lib/clap"),
          "clap_path defaults to ~/.clap, then /usr/lib/clap");
    check(!*conf.lv2_extra, "lv2_extra is empty by default");
    check(conf_merge_extra(&conf) == 0 && where(conf.lv2_path, "/usr/lib/lv2") == 0, "no extra leaves lv2_path as it is");

    setenv("LV2_PATH", "/site/lv2", 1);
    conf_defaults(&conf);
    check(!strcmp(conf.lv2_path, "/site/lv2"), "$LV2_PATH stands in for the default list");
    snprintf(conf.lv2_extra, sizeof(conf.lv2_extra), "/zynthian/plugins/lv2:/zynthian/presets/lv2");
    check(conf_merge_extra(&conf) == 0 && !strcmp(conf.lv2_path, "/site/lv2:/zynthian/plugins/lv2:/zynthian/presets/lv2"),
          "lv2_extra is searched after lv2_path");
    unsetenv("LV2_PATH");

    setenv("CLAP_PATH", "/site/clap", 1);
    conf_defaults(&conf);
    check(starts_with_dirs(conf.clap_path, "/site/clap") &&
              !strcmp(conf.clap_path + strlen("/site/clap:"), PHD_DEFAULT_CLAP_PATH),
          "$CLAP_PATH is searched before the default");
    unsetenv("CLAP_PATH");

    /* an integer setting holds a whole number and nothing else (plugin-hostd#146 3): a word that is not one is a bad
     * setting, not 0 */
    {
        static const char *const bad[] = { "checkpoint_ms abc\n", "checkpoint_ms 5x\n", "checkpoint_ms \n" };
        char path[] = "/tmp/plugin-hostd-conf-test.XXXXXX";
        int fd = mkstemp(path);

        for (k = 0; fd >= 0 && k < 3; k++)
        {
            FILE *f = fopen(path, "w");

            fputs(bad[k], f);
            fclose(f);
            conf_defaults(&conf);
            check(conf_load(&conf, path, 1) != 0, bad[k]);
        }
        /* a line longer than the reader's buffer is refused whole: its tail is never read as a setting of its own */
        {
            FILE *f = fopen(path, "w");
            int n;

            fputc('#', f);
            for (n = 1; n < PATH_MAX * 2 + 64 - 1; n++)
                fputc('x', f);
            fputs("checkpoint_ms 5\n", f);
            fclose(f);
            conf_defaults(&conf);
            check(conf_load(&conf, path, 1) != 0 && conf.checkpoint_ms != 5,
                  "an overlong line is refused, its tail not read as checkpoint_ms 5");
        }
        if (fd >= 0)
        {
            close(fd);
            unlink(path);
        }
        check(fd >= 0, "a scratch file for the conf");
    }

    if (failures)
        printf("conf: %d failed\n", failures);
    else
        printf("ok   conf_test\n");
    return failures ? 1 : 0;
}
