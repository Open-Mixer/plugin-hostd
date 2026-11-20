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

/** @file probe_words.h
 * @brief The words a probe run writes, which plugin-hostd-protocol's probe domain (its contract.d/probe/probe.json, shipped by
 * plugin-hostd-protocol-contract) holds: the run's reason, the outcome of a step and of the run, the steps, and the signal a child
 * died of.
 *
 * The ids come from the protocol header's own lists (PHD_PROBE_REASONS, PHD_PROBE_OUTCOMES, PHD_PROBE_STEPS) and, for the
 * signals, the domain's own codes header (include/plugin-hostd/probe_codes.h, the render of PROBE_SIGNALS); the word of
 * an id is the domain's word at the id's place, read once at start-up, so no word is a literal of the probe.
 */

#ifndef PROBE_WORDS_H
#define PROBE_WORDS_H

#include <omxcontract/omx_domain.h>
#include <plugin-hostd/probe_codes.h>
#include <plugin-hostd/protocol.h>
#include <signal.h>
#include <stddef.h>

/** the domain the words are read from */
#define PROBE_DOMAIN "probe"
/** the lowest info.version of the probe domain this package reads */
#define PROBE_FLOOR "1.0.0"

/** the reasons of a run, the places of the words of PROBE_REASONS */
enum probe_reason
{
/** one row of PHD_PROBE_REASONS: its enum constant */
#define X(id, code, meaning) PROBE_REASON_##id,
    PHD_PROBE_REASONS(X)
#undef X
    PROBE_REASON_COUNT
};

/** the outcomes of a step or a run, the places of the words of PROBE_OUTCOMES */
enum probe_outcome
{
/** one row of PHD_PROBE_OUTCOMES: its enum constant */
#define X(id, code, meaning) PROBE_OUTCOME_##id,
    PHD_PROBE_OUTCOMES(X)
#undef X
    PROBE_OUTCOME_COUNT
};

/** the steps of a run, the places of the words of PROBE_STEPS */
enum probe_step
{
/** one row of PHD_PROBE_STEPS: its enum constant */
#define X(id, code, meaning) PROBE_STEP_##id,
    PHD_PROBE_STEPS(X)
#undef X
    PROBE_STEP_COUNT
};

/** The words, read once at start-up from the probe domain; they point into the open handle, which lives until
 * probe_words_close(). */
typedef struct
{
    omx_domain *domain;                         /**< the open probe domain, which owns the words */
    const char *reason[PROBE_REASON_COUNT];     /**< the PROBE_REASONS words, by enum probe_reason */
    const char *outcome[PROBE_OUTCOME_COUNT];   /**< the PROBE_OUTCOMES words, by enum probe_outcome */
    const char *step[PROBE_STEP_COUNT];         /**< the PROBE_STEPS words, by enum probe_step */
    const char *signal[OMX_PROBE_SIGNALS_COUNT]; /**< the PROBE_SIGNALS words, by the domain's codes (OMX_PROBE_SIGNALS_*) */
} probe_words;

/**
 * Open the probe domain and read its words.
 *
 * @param dirs the directories to read it from (a ':' list, the first holding it wins: a command-line tool's test entry), or
 *             NULL for the installed contract directory
 * @param w    receives the words
 * @param why  receives the refusal, naming the domain, the loader's code and the floor or the item, when the open fails
 * @param n    the size of why
 * @return 0, or the OMX_CONTRACT_CODE_* value of the refusal; the caller ends its start-up with 78
 */
int probe_words_open(const char *dirs, probe_words *w, char *why, size_t n);

/**
 * Release the handle, and with it the words.
 *
 * @param w the words probe_words_open() filled; closing twice is harmless
 */
void probe_words_close(probe_words *w);

/**
 * The word for a signal.
 *
 * @param w   the words
 * @param sig a signal number
 * @return the PROBE_SIGNALS word of the signal, the word for any other signal when the probe has no name for it
 */
const char *probe_signal_word(const probe_words *w, int sig);

#endif
