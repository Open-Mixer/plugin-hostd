// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#ifndef MACHINE_VOCABULARY_H
#define MACHINE_VOCABULARY_H
/*
 * GENERATED: DO NOT EDIT BY HAND.
 * Produced by `omx-contract render --target c` from Open-Mixer/machine's data/: the vocabulary
 * (docs/data-layout.md). A code is OMX_ and the code in upper snake case, and a reply code that carries a resp has it as that name and _RESP; a word is OMX_<ITEM>_<NAME>, each words
 * item with its _COUNT and an _INIT of its words in their order. A consumer writes and compares these, never a
 * literal of its own.
 */

/** @file
 * @brief The vocabulary of machine: every code and every word as a string define, with its sentence
 * where it carries one. */

/* MACHINE_CLASS_FIELDS (machine/machine.json) */
#define OMX_MACHINE_CLASS_FIELDS_ARCH "arch" ///< The machine architecture as uname -m names it.
/** The source sentence (English) of OMX_MACHINE_CLASS_FIELDS_ARCH. */
#define OMX_MACHINE_CLASS_FIELDS_ARCH_TEXT_EN "The machine architecture, as uname -m names it."
#define OMX_MACHINE_CLASS_FIELDS_FAMILY "family" ///< The CPU family and model.
/** The source sentence (English) of OMX_MACHINE_CLASS_FIELDS_FAMILY. */
#define OMX_MACHINE_CLASS_FIELDS_FAMILY_TEXT_EN "The CPU family and model."
#define OMX_MACHINE_CLASS_FIELDS_CORE_BAND "coreBand" ///< The cores, as a band of MACHINE_CORE_BANDS.
/** The source sentence (English) of OMX_MACHINE_CLASS_FIELDS_CORE_BAND. */
#define OMX_MACHINE_CLASS_FIELDS_CORE_BAND_TEXT_EN "The core count, as a band of MACHINE_CORE_BANDS."
#define OMX_MACHINE_CLASS_FIELDS_CLOCK_BAND "clockBand" ///< The clock, as a band of MACHINE_CLOCK_BANDS.
/** The source sentence (English) of OMX_MACHINE_CLASS_FIELDS_CLOCK_BAND. */
#define OMX_MACHINE_CLASS_FIELDS_CLOCK_BAND_TEXT_EN "The clock, as a band of MACHINE_CLOCK_BANDS."
#define OMX_MACHINE_CLASS_FIELDS_PREEMPT_RT "preemptRt" ///< Whether the kernel is PREEMPT_RT.
/** The source sentence (English) of OMX_MACHINE_CLASS_FIELDS_PREEMPT_RT. */
#define OMX_MACHINE_CLASS_FIELDS_PREEMPT_RT_TEXT_EN "Whether the kernel is PREEMPT_RT."
#define OMX_MACHINE_CLASS_FIELDS_CSTATES_LIMITED "cstatesLimited" ///< Whether the deep idle states are limited.
/** The source sentence (English) of OMX_MACHINE_CLASS_FIELDS_CSTATES_LIMITED. */
#define OMX_MACHINE_CLASS_FIELDS_CSTATES_LIMITED_TEXT_EN "Whether the deep idle states are limited."
/** The number of words of MACHINE_CLASS_FIELDS. */
#define OMX_MACHINE_CLASS_FIELDS_COUNT 6u
/** The words of MACHINE_CLASS_FIELDS in their declared order, as a C initializer list. */
#define OMX_MACHINE_CLASS_FIELDS_INIT { "arch", "family", "coreBand", "clockBand", "preemptRt", "cstatesLimited" }
/** Expands `X(code, "word", NAME)` once per word of MACHINE_CLASS_FIELDS, in order, the code being its place in the order. What identifies the machine a figure was taken on (plugin-qualify#115): a verdict for a host profile reads only figures of the class it names. */
#define OMX_MACHINE_CLASS_FIELDS(X) \
    X(0u, "arch", ARCH) X(1u, "family", FAMILY) X(2u, "coreBand", CORE_BAND) X(3u, "clockBand", CLOCK_BAND) \
    X(4u, "preemptRt", PREEMPT_RT) X(5u, "cstatesLimited", CSTATES_LIMITED)

/* MACHINE_PROFILE_FIELDS (machine/machine.json) */
#define OMX_MACHINE_PROFILE_FIELDS_GOVERNOR "governor"
/** The source sentence (English) of OMX_MACHINE_PROFILE_FIELDS_GOVERNOR. */
#define OMX_MACHINE_PROFILE_FIELDS_GOVERNOR_TEXT_EN "The CPU frequency governor in effect when the figure was taken."
#define OMX_MACHINE_PROFILE_FIELDS_TURBO "turbo"
/** The source sentence (English) of OMX_MACHINE_PROFILE_FIELDS_TURBO. */
#define OMX_MACHINE_PROFILE_FIELDS_TURBO_TEXT_EN "Whether turbo or boost clocking was enabled when the figure was taken."
#define OMX_MACHINE_PROFILE_FIELDS_SMT "smt"
/** The source sentence (English) of OMX_MACHINE_PROFILE_FIELDS_SMT. */
#define OMX_MACHINE_PROFILE_FIELDS_SMT_TEXT_EN "Whether simultaneous multithreading was enabled when the figure was taken."
#define OMX_MACHINE_PROFILE_FIELDS_PREEMPT "preempt"
/** The source sentence (English) of OMX_MACHINE_PROFILE_FIELDS_PREEMPT. */
#define OMX_MACHINE_PROFILE_FIELDS_PREEMPT_TEXT_EN "Whether the measuring thread ran under real-time preemption, or scheduled as any other thread."
#define OMX_MACHINE_PROFILE_FIELDS_CPUIDLE "cpuidle"
/** The source sentence (English) of OMX_MACHINE_PROFILE_FIELDS_CPUIDLE. */
#define OMX_MACHINE_PROFILE_FIELDS_CPUIDLE_TEXT_EN "The CPU idle driver or policy in effect when the figure was taken."
/** The number of words of MACHINE_PROFILE_FIELDS. */
#define OMX_MACHINE_PROFILE_FIELDS_COUNT 5u
/** The words of MACHINE_PROFILE_FIELDS in their declared order, as a C initializer list. */
#define OMX_MACHINE_PROFILE_FIELDS_INIT { "governor", "turbo", "smt", "preempt", "cpuidle" }
/** Expands `X(code, "word", NAME)` once per word of MACHINE_PROFILE_FIELDS, in order, the code being its place in the order. How the machine was set when a figure was taken: the frequency policy and isolation a figure depends on. */
#define OMX_MACHINE_PROFILE_FIELDS(X) \
    X(0u, "governor", GOVERNOR) X(1u, "turbo", TURBO) X(2u, "smt", SMT) X(3u, "preempt", PREEMPT) \
    X(4u, "cpuidle", CPUIDLE)

/* MACHINE_CORE_BANDS (machine/machine.json) */
#define OMX_MACHINE_CORE_BANDS_CORES1_TO2 "1-2"
/** The source sentence (English) of OMX_MACHINE_CORE_BANDS_CORES1_TO2. */
#define OMX_MACHINE_CORE_BANDS_CORES1_TO2_TEXT_EN "A machine with 1 to 2 cores."
#define OMX_MACHINE_CORE_BANDS_CORES3_TO4 "3-4"
/** The source sentence (English) of OMX_MACHINE_CORE_BANDS_CORES3_TO4. */
#define OMX_MACHINE_CORE_BANDS_CORES3_TO4_TEXT_EN "A machine with 3 to 4 cores."
#define OMX_MACHINE_CORE_BANDS_CORES5_TO8 "5-8"
/** The source sentence (English) of OMX_MACHINE_CORE_BANDS_CORES5_TO8. */
#define OMX_MACHINE_CORE_BANDS_CORES5_TO8_TEXT_EN "A machine with 5 to 8 cores."
#define OMX_MACHINE_CORE_BANDS_CORES9_TO16 "9-16"
/** The source sentence (English) of OMX_MACHINE_CORE_BANDS_CORES9_TO16. */
#define OMX_MACHINE_CORE_BANDS_CORES9_TO16_TEXT_EN "A machine with 9 to 16 cores."
#define OMX_MACHINE_CORE_BANDS_CORES17_TO32 "17-32"
/** The source sentence (English) of OMX_MACHINE_CORE_BANDS_CORES17_TO32. */
#define OMX_MACHINE_CORE_BANDS_CORES17_TO32_TEXT_EN "A machine with 17 to 32 cores."
#define OMX_MACHINE_CORE_BANDS_CORES33_UP "33+"
/** The source sentence (English) of OMX_MACHINE_CORE_BANDS_CORES33_UP. */
#define OMX_MACHINE_CORE_BANDS_CORES33_UP_TEXT_EN "A machine with 33 or more cores."
/** The number of words of MACHINE_CORE_BANDS. */
#define OMX_MACHINE_CORE_BANDS_COUNT 6u
/** The words of MACHINE_CORE_BANDS in their declared order, as a C initializer list. */
#define OMX_MACHINE_CORE_BANDS_INIT { "1-2", "3-4", "5-8", "9-16", "17-32", "33+" }
/** Expands `X(code, "word", NAME)` once per word of MACHINE_CORE_BANDS, in order, the code being its place in the order. The bands a machine's core count falls in, ascending. */
#define OMX_MACHINE_CORE_BANDS(X) \
    X(0u, "1-2", CORES1_TO2) X(1u, "3-4", CORES3_TO4) X(2u, "5-8", CORES5_TO8) X(3u, "9-16", CORES9_TO16) \
    X(4u, "17-32", CORES17_TO32) X(5u, "33+", CORES33_UP)

/* MACHINE_CLOCK_BANDS (machine/machine.json) */
#define OMX_MACHINE_CLOCK_BANDS_UNDER1500_MHZ "<1.5GHz"
/** The source sentence (English) of OMX_MACHINE_CLOCK_BANDS_UNDER1500_MHZ. */
#define OMX_MACHINE_CLOCK_BANDS_UNDER1500_MHZ_TEXT_EN "A machine clocked under 1.5 GHz."
#define OMX_MACHINE_CLOCK_BANDS_FROM1500_TO2500_MHZ "1.5-2.5GHz"
/** The source sentence (English) of OMX_MACHINE_CLOCK_BANDS_FROM1500_TO2500_MHZ. */
#define OMX_MACHINE_CLOCK_BANDS_FROM1500_TO2500_MHZ_TEXT_EN "A machine clocked from 1.5 to 2.5 GHz."
#define OMX_MACHINE_CLOCK_BANDS_FROM2500_TO3500_MHZ "2.5-3.5GHz"
/** The source sentence (English) of OMX_MACHINE_CLOCK_BANDS_FROM2500_TO3500_MHZ. */
#define OMX_MACHINE_CLOCK_BANDS_FROM2500_TO3500_MHZ_TEXT_EN "A machine clocked from 2.5 to 3.5 GHz."
#define OMX_MACHINE_CLOCK_BANDS_FROM3500_TO4500_MHZ "3.5-4.5GHz"
/** The source sentence (English) of OMX_MACHINE_CLOCK_BANDS_FROM3500_TO4500_MHZ. */
#define OMX_MACHINE_CLOCK_BANDS_FROM3500_TO4500_MHZ_TEXT_EN "A machine clocked from 3.5 to 4.5 GHz."
#define OMX_MACHINE_CLOCK_BANDS_FROM4500_MHZ "4.5GHz+"
/** The source sentence (English) of OMX_MACHINE_CLOCK_BANDS_FROM4500_MHZ. */
#define OMX_MACHINE_CLOCK_BANDS_FROM4500_MHZ_TEXT_EN "A machine clocked at 4.5 GHz or more."
/** The number of words of MACHINE_CLOCK_BANDS. */
#define OMX_MACHINE_CLOCK_BANDS_COUNT 5u
/** The words of MACHINE_CLOCK_BANDS in their declared order, as a C initializer list. */
#define OMX_MACHINE_CLOCK_BANDS_INIT { "<1.5GHz", "1.5-2.5GHz", "2.5-3.5GHz", "3.5-4.5GHz", "4.5GHz+" }
/** Expands `X(code, "word", NAME)` once per word of MACHINE_CLOCK_BANDS, in order, the code being its place in the order. The bands a machine's clock falls in, ascending. */
#define OMX_MACHINE_CLOCK_BANDS(X) \
    X(0u, "<1.5GHz", UNDER1500_MHZ) X(1u, "1.5-2.5GHz", FROM1500_TO2500_MHZ) X(2u, "2.5-3.5GHz", FROM2500_TO3500_MHZ) X(3u, "3.5-4.5GHz", FROM3500_TO4500_MHZ) \
    X(4u, "4.5GHz+", FROM4500_MHZ)

/* MACHINE_ARCHES (machine/machine.json) */
#define OMX_MACHINE_ARCHES_X8664 "x86_64"
/** The source sentence (English) of OMX_MACHINE_ARCHES_X8664. */
#define OMX_MACHINE_ARCHES_X8664_TEXT_EN "An x86-64 machine, as uname -m spells it."
#define OMX_MACHINE_ARCHES_AARCH64 "aarch64"
/** The source sentence (English) of OMX_MACHINE_ARCHES_AARCH64. */
#define OMX_MACHINE_ARCHES_AARCH64_TEXT_EN "An AArch64 machine, as uname -m spells it."
/** The number of words of MACHINE_ARCHES. */
#define OMX_MACHINE_ARCHES_COUNT 2u
/** The words of MACHINE_ARCHES in their declared order, as a C initializer list. */
#define OMX_MACHINE_ARCHES_INIT { "x86_64", "aarch64" }
/** Expands `X(code, "word", NAME)` once per word of MACHINE_ARCHES, in order, the code being its place in the order. The architectures a host profile names, as uname -m spells them. */
#define OMX_MACHINE_ARCHES(X) \
    X(0u, "x86_64", X8664) X(1u, "aarch64", AARCH64)

#endif /* MACHINE_VOCABULARY_H */
