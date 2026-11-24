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

/** @file machine.h
 * @brief The declarations of machine.h.
 */

#ifndef MACHINE_H
#define MACHINE_H

#include <omxcontract/omx_domain.h>
#include <plugin-hostd/machine_codes.h>
#include <stddef.h>

/** the domain the band words are read from */
#define MACHINE_DOMAIN "machine"
/** the lowest info.version of the machine domain this package reads */
#define MACHINE_FLOOR "1.1.0"
/** the core bands machine_bands() cuts: the words of MACHINE_CORE_BANDS at these indexes, in order (the domain's count) */
#define MACHINE_CORE_BAND_COUNT ((int)OMX_MACHINE_CORE_BANDS_COUNT)
/** the clock bands machine_bands() cuts: the words of MACHINE_CLOCK_BANDS at these indexes, in order (the domain's count) */
#define MACHINE_CLOCK_BAND_COUNT ((int)OMX_MACHINE_CLOCK_BANDS_COUNT)
/** the families the probe names a CPU by, the words of MACHINE_FAMILIES at these indexes: the domain's codes */
enum machine_family
{
    MACHINE_FAMILY_INTEL = OMX_MACHINE_FAMILIES_INTEL,
    MACHINE_FAMILY_AMD = OMX_MACHINE_FAMILIES_AMD,
    MACHINE_FAMILY_ARM = OMX_MACHINE_FAMILIES_ARM,
    MACHINE_FAMILY_UNKNOWN = OMX_MACHINE_FAMILIES_UNKNOWN,
    MACHINE_FAMILY_COUNT = OMX_MACHINE_FAMILIES_COUNT
};

/** The band and family words, read once at start-up from the machine domain (contract.d/machine/machine.json, shipped by
 * plugin-hostd-contract); they point into the open handle, which lives until machine_words_close(). */
typedef struct
{
    omx_domain *domain;                          /**< the open machine domain, which owns the words */
    const char *core[MACHINE_CORE_BAND_COUNT];   /**< the MACHINE_CORE_BANDS words, by band index */
    const char *clock[MACHINE_CLOCK_BAND_COUNT]; /**< the MACHINE_CLOCK_BANDS words, by band index */
    const char *family[MACHINE_FAMILY_COUNT];    /**< the MACHINE_FAMILIES words, by enum machine_family */
} machine_words;

/**
 * Open the machine domain and take the band words.
 *
 * @param dirs NULL for the installed contract directory (the packaged daemon's entry); else a ':' list, the first
 *             directory that holds the domain wins (a command-line tool's OMX_CONTRACT_PATH, or a test build's tree)
 * @param w    receives the words
 * @param why  receives the refusal, naming the domain, the loader's code and the floor or the item, when the open fails
 * @param n    the size of why
 * @return 0, or the OMX_CONTRACT_CODE_* value of the refusal; the caller ends its start-up with 78
 */
int machine_words_open(const char *dirs, machine_words *w, char *why, size_t n);

/**
 * Release the handle, and with it the words.
 *
 * @param w the words machine_words_open() filled; closing twice is harmless
 */
void machine_words_close(machine_words *w);

/**
 * The machine class the probe writes (the domain's MACHINE_CORE_BANDS and MACHINE_CLOCK_BANDS). The thresholds are
 * code, the words are the domain's, the one at the band's index in `w`.
 *
 * @param w          the band words
 * @param ncpu       the number of cores
 * @param khz        the highest clock the first core states, in kHz (0 when it states none)
 * @param core_band  receives the core band's word
 * @param clock_band receives the clock band's word
 */
void machine_bands(const machine_words *w, long ncpu, long khz, const char **core_band, const char **clock_band);

/**
 * This machine's class as one word, arch/cores/clock (x86_64/5-8/2.5-3.5GHz): uname's machine, the online cores' band
 * and cpu0's cpuinfo_max_freq's band.
 *
 * @param w    the band words
 * @param out  receives the word
 * @param size the size of out
 * @return 0, or -1 when `size` is too small
 */
int machine_class(const machine_words *w, char *out, size_t size);

#endif
