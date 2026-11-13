/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * plugin-hostd is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * plugin-hostd is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with plugin-hostd.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/* THE MUTANT AND BREAKAGE RECORDS of the two libFuzzer harnesses (fuzz/fuzz_command.c, fuzz/fuzz_reply.c,
 * fuzz/recorder.c), kept in this one file under src/ instead of beside each check: a check names its record with one
 * `record: <key>` comment, and fuzz/checks.awk reads the key's block below, by that key, from here. Moving them here
 * means a record is never hand-copied into two places (the check that names it, and the check itself were the same
 * place before this), and fuzz/checks.awk's ratchet over this file is the one place a record can go stale.
 *
 * A block is introduced by `record: <key>` and holds one `mutant:`/`input:` pair or more, the same shape
 * fuzz/checks.awk has always read (fuzz/README.md, "The checks of a fuzz target"):
 *
 *   record: <key>
 *   mutant: <path>:<line> `<old>` -> `<new>`
 *   input: <a seed of the harness's corpus>
 *
 * one pair or more. Every key here is named by exactly one check; fuzz/checks.awk refuses a key with no block, a
 * block with no key naming it, and a check with neither a `record:` nor a `not a property:` line of its own (a stop
 * that needs no seed stays where it is, since it names no file to point here at). */

#ifndef PLUGIN_HOSTD_FUZZ_RECORDS_H
#define PLUGIN_HOSTD_FUZZ_RECORDS_H

/* record: reply-answer-unchanged
 * mutant: src/verbs.c:151 `text, strlen(text) + 1` -> `text + 1, strlen(text)`
 * input: add-default
 * mutant: src/verbs.c:86 `return pins_set(tok[1], tok[2], tok[3], verdict, pool);` -> `pins_set(tok[1], tok[2], tok[3], verdict, pool); return SUCCESS;`
 * input: plugin-hostd-pin_set-refused
 * mutant: src/verbs.c:325 `return reply_text;` -> `return sup_resp(SUCCESS);`
 * input: mod-host-set_bpm-refused */

/* record: reply-answer-self-made
 * mutant: src/verbs.c:216 `return sup_resp(ERR_INVALID_OPERATION);` -> `return sup_resp(SUCCESS);`
 * input: add-too-few
 * mutant: src/verbs.c:306 `!strcmp(verb, QUIT)` -> `verb_is(verb, QUIT)`
 * input: quit-quoted-with-a-space
 * mutant: src/verbs.c:306 `!strcmp(verb, QUIT)` -> `!strncmp(verb, QUIT, strlen(QUIT))`
 * input: quit-prefix */

/* record: call-of-verb
 * mutant: src/verbs.c:237 `atoi(tok[1]) == -1 ? sup_remove_all() : sup_remove(atoi(tok[1]))` -> `sup_remove_all()`
 * input: mod-host-remove
 * mutant: src/verbs.c:230 `descriptors_get(tok[1])` -> `descriptors_panel_get(tok[1])`
 * input: plugin-hostd-descriptor_get */

/* record: reply-hello-no-worker
 * mutant: src/verbs.c:164 `strcmp(verb, OMX_VERB_HELLO)` -> `strcmp(verb, "hello_")`
 * input: hello-tags */

/* record: reply-hello-shape
 * mutant: src/verbs.c:165 `ntok < 2 ? strdup(MESSAGE_FEW_ARGUMENTS)` -> `ntok < 2 ? sup_resp(SUCCESS)`
 * input: hello-no-version */

/* record: reply-tagged-no-worker
 * mutant: src/verbs.c:166 `verb[0] == '@'` -> `verb[0] == '\1'`
 * input: tagged-command */

/* record: reply-tagged-answer
 * mutant: src/verbs.c:167 `strdup(MESSAGE_COMMAND_NOT_FOUND)` -> `sup_resp(ERR_INVALID_OPERATION)`
 * input: tagged-command
 * mutant: src/verbs.c:167 `strdup(MESSAGE_COMMAND_NOT_FOUND)` -> `strdup("resp 0")`
 * input: tagged-nothing-after */

/* record: reply-one-reply
 * mutant: src/verbs.c:515 `reply(fd, text, tag, tag_len);` -> `free(text);`
 * input: add-default */

/* record: reply-nul-terminated
 * mutant: src/verbs.c:151 `strlen(text) + 1` -> `strlen(text)`
 * input: add-default */

/* record: reply-refusal-shape
 * mutant: src/verbs.c:83 `return ERR_INVALID_OPERATION;` -> `return -7777;`
 * input: pin-set-layout-unknown */

/* record: reply-declared-shape
 * mutant: src/verbs.c:311 `sup_resp(SUCCESS)` -> `sup_resp(1)`
 * input: mod-host-quit */

/* record: arity-declared-count
 * mutant: src/verbs.c:256 `ntok == 3` -> `ntok >= 3`
 * input: plugin-hostd-pool_config-extra
 * mutant: src/verbs.c:233 `verb_is(verb, EFFECT_REMOVE)` -> `verb_is(verb, EFFECT_REMOVE) && ntok == 2`
 * input: mod-host-remove-extra */

/* record: words-add-uri-instance
 * mutant: src/verbs.c:223 `atoi(tok[at])` -> `atoi(tok[1])`
 * input: add-instance-past-the-table */

/* record: words-add-placement-client
 * mutant: src/verbs.c:223 `placement, client` -> `client, placement`
 * input: add-pool-p-fuzz_client */

/* record: words-scan-uri
 * mutant: src/verbs.c:226 `descriptors_add(uri);` -> `descriptors_add(tok[1]);`
 * input: add-clap-path-with-a-space */

/* record: words-chain-members
 * mutant: src/verbs.c:111 `ntok - 2` -> `ntok - 3`
 * input: plugin-hostd-chain */

/* record: words-pin-set-verdict-pool
 * mutant: src/pin_words.c:49 `word[k] + key` -> `word[k]`
 * input: plugin-hostd-pin_set-full */

/* record: words-call-argument
 * mutant: src/verbs.c:237 `sup_remove(atoi(tok[1]))` -> `sup_remove(atoi(tok[1]) + 1)`
 * input: mod-host-remove */

/* record: refusal-state-unchanged
 * mutant: src/verbs.c:225 `reply_text && sup_reply_code(reply_text) >= 0` -> `reply_text`
 * input: add-instance-past-the-table */

/* record: round-trip-same-calls
 * mutant: src/words.c:42 `*p == '\t' || *p == '\r'` -> `*p == '\r'`
 * input: mod-host-add-tabs */

/* record: round-trip-same-reply
 * mutant: src/verbs.c:308 `ntok != 1` -> `ntok != 1 || line[0] != ' '`
 * input: quit-leading-space */

/* record: round-trip-same-state
 * mutant: src/verbs.c:310 `g_quitting = 1;` -> `g_quitting = line[0] == ' ';`
 * input: quit-leading-space */

/* record: answer-fits-one-line
 * mutant: include/plugin-hostd/protocol.h:78 `4096` -> `4`
 * input: mod-host-bypass */

/* record: relay-socket-client-only
 * mutant: src/relay.c:114 `send(g_client, line + sent` -> `send(g_client + 1, line + sent`
 * input: lines */

/* record: relay-bounded-unfinished
 * mutant: src/relay.c:341 `s->used > LINE_LIMIT` -> `s->used > s->cap`
 * input: line-past-the-limit-in-parts */

/* record: relay-bounded-capacity
 * mutant: src/relay.c:300 `s->cap * 2` -> `s->cap * 3`
 * input: buffer-grows */

/* record: relay-shape-whole-line
 * mutant: src/relay.c:535 `strlen(line) + 1` -> `strlen(line)`
 * input: event */

/* record: relay-no-loss-present
 * mutant: src/relay.c:327 `> LINE_LIMIT` -> `>= LINE_LIMIT`
 * input: line-at-the-limit */

/* record: relay-no-loss-content
 * mutant: src/relay.c:331 `start, nul - start + 1` -> `start + 1, nul - start`
 * input: lines */

/* record: relay-no-loss-read
 * mutant: src/relay.c:659 `drain(&g_src[i]);` -> `;`
 * input: written-then-removed
 * mutant: src/relay.c:633 `drain(&g_src[i]);` -> `;`
 * input: written-then-instance-gone */

/* record: relay-shape-ends-present
 * mutant: src/relay.c:258 `gesture_end(s->held[n]);` -> ``
 * input: gesture-held-then-removed */

/* record: relay-shape-ends-suffix
 * mutant: src/relay.c:248 `" " PHD_GESTURE_END, sizeof(" " PHD_GESTURE_END)` -> `" " PHD_GESTURE_BEGIN, sizeof(" " PHD_GESTURE_BEGIN)`
 * input: gesture-held-then-removed */

/* record: relay-shape-ends-held
 * mutant: src/relay.c:247 `strlen(held)` -> `strlen(held) - 1`
 * input: gesture-held-then-removed */

/* record: relay-shape-done
 * mutant: src/relay.c:535 `send_line(line, strlen(line) + 1);` -> `send_line(line, strlen(line) + 1); send_line(line, strlen(line) + 1);`
 * input: event */

/* record: relay-shape-event-present
 * mutant: src/relay.c:535 `send_line(line, strlen(line) + 1);` -> ``
 * input: event */

/* record: relay-shape-event-content
 * mutant: src/relay.c:535 `line, strlen(line) + 1` -> `line + 1, strlen(line)`
 * input: event */

/* record: relay-follows-worker
 * mutant: src/relay.c:541 `fd < 0` -> `fd >= 0`
 * input: lines */

/* record: relay-holds-each-worker
 * mutant: src/relay.c:562 `g_src[g_nsrc++].fd = fd;` -> `g_src[g_nsrc].fd = fd;`
 * input: lines */

/* record: relay-eof-is-the-end
 * mutant: src/relay.c:318 `if (n == 0 || (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK))` -> `if (n <= 0)`
 * input: lines */

#endif
