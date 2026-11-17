// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#ifndef QUALIFICATION_VOCABULARY_H
#define QUALIFICATION_VOCABULARY_H
/*
 * GENERATED: DO NOT EDIT BY HAND.
 * Produced by `omx-contract render --target c` from Open-Mixer/qualification's data/: the vocabulary
 * (docs/data-layout.md). A code is OMX_ and the code in upper snake case, and a reply code that carries a resp has it as that name and _RESP; a word is OMX_<ITEM>_<NAME>, each words
 * item with its _COUNT and an _INIT of its words in their order. A consumer writes and compares these, never a
 * literal of its own.
 */

/** @file
 * @brief The vocabulary of qualification: every code and every word as a string define, with its sentence
 * where it carries one. */

/* MEASUREMENT_DIMENSIONS (qualification/qualification.json) */
#define OMX_MEASUREMENT_DIMENSIONS_LATENCY "latency"
/** The source sentence (English) of OMX_MEASUREMENT_DIMENSIONS_LATENCY. */
#define OMX_MEASUREMENT_DIMENSIONS_LATENCY_TEXT_EN "How long a plugin takes to produce its first sound after it is driven or played."
#define OMX_MEASUREMENT_DIMENSIONS_COST "cost"
/** The source sentence (English) of OMX_MEASUREMENT_DIMENSIONS_COST. */
#define OMX_MEASUREMENT_DIMENSIONS_COST_TEXT_EN "How much CPU time a plugin spends per block under a sustained stimulus."
#define OMX_MEASUREMENT_DIMENSIONS_STABILITY "stability"
/** The source sentence (English) of OMX_MEASUREMENT_DIMENSIONS_STABILITY. */
#define OMX_MEASUREMENT_DIMENSIONS_STABILITY_TEXT_EN "Whether a plugin instantiates, processes and tears down without crashing or producing non-finite output."
#define OMX_MEASUREMENT_DIMENSIONS_RT_SAFETY "rtSafety"
/** The source sentence (English) of OMX_MEASUREMENT_DIMENSIONS_RT_SAFETY. */
#define OMX_MEASUREMENT_DIMENSIONS_RT_SAFETY_TEXT_EN "Whether a plugin's audio thread avoids locks, allocation and other calls a real-time thread must not make."
#define OMX_MEASUREMENT_DIMENSIONS_FEATURES "features"
/** The source sentence (English) of OMX_MEASUREMENT_DIMENSIONS_FEATURES. */
#define OMX_MEASUREMENT_DIMENSIONS_FEATURES_TEXT_EN "What capabilities a plugin declares and a prober can confirm, beside latency, cost, stability and RT safety."
/** The number of words of MEASUREMENT_DIMENSIONS. */
#define OMX_MEASUREMENT_DIMENSIONS_COUNT 5u
/** The words of MEASUREMENT_DIMENSIONS in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_DIMENSIONS_INIT { "latency", "cost", "stability", "rtSafety", "features" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_DIMENSIONS, in order, the code being its place in the order. The measurable dimensions a measurement document declares it covers: latency and cost since the format's 1.0, stability, RT safety and features since 1.1, for the hosting verdict. */
#define OMX_MEASUREMENT_DIMENSIONS(X) \
    X(0u, "latency", LATENCY) X(1u, "cost", COST) X(2u, "stability", STABILITY) X(3u, "rtSafety", RT_SAFETY) \
    X(4u, "features", FEATURES)

/* MEASUREMENT_UNMEASURED_KINDS (qualification/qualification.json) */
#define OMX_MEASUREMENT_UNMEASURED_KINDS_NOTHING_TO_MEASURE "nothing-to-measure" ///< A property of the plugin: any prober on any machine reaches it, so it may override a figure.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_KINDS_NOTHING_TO_MEASURE. */
#define OMX_MEASUREMENT_UNMEASURED_KINDS_NOTHING_TO_MEASURE_TEXT_EN "A property of the plugin: any prober on any machine reaches it, so it may override a figure."
#define OMX_MEASUREMENT_UNMEASURED_KINDS_PROBE_FAILED "probe-failed" ///< A property of this run: it says nothing about the plugin and never overrides a figure.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_KINDS_PROBE_FAILED. */
#define OMX_MEASUREMENT_UNMEASURED_KINDS_PROBE_FAILED_TEXT_EN "A property of this run: it says nothing about the plugin and never overrides a figure."
#define OMX_MEASUREMENT_UNMEASURED_KINDS_NOT_ATTEMPTED "not-attempted" ///< The run did not cover this plugin or this dimension: a partial run, not a finding.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_KINDS_NOT_ATTEMPTED. */
#define OMX_MEASUREMENT_UNMEASURED_KINDS_NOT_ATTEMPTED_TEXT_EN "The run did not cover this plugin or this dimension: a partial run, not a finding."
/** The number of words of MEASUREMENT_UNMEASURED_KINDS. */
#define OMX_MEASUREMENT_UNMEASURED_KINDS_COUNT 3u
/** The words of MEASUREMENT_UNMEASURED_KINDS in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_UNMEASURED_KINDS_INIT { "nothing-to-measure", "probe-failed", "not-attempted" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_UNMEASURED_KINDS, in order, the code being its place in the order. What an absent figure means for a merge, the one distinction that changes behaviour: a property of the plugin, a failure of this run, or a dimension the run did not cover. */
#define OMX_MEASUREMENT_UNMEASURED_KINDS(X) \
    X(0u, "nothing-to-measure", NOTHING_TO_MEASURE) X(1u, "probe-failed", PROBE_FAILED) X(2u, "not-attempted", NOT_ATTEMPTED)

/* MEASUREMENT_UNMEASURED_REASONS (qualification/qualification.json) */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NO_AUDIO_IN "no-audio-in" ///< No audio input port: nothing to drive.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NO_AUDIO_IN. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NO_AUDIO_IN_TEXT_EN "No audio input port: nothing to drive."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NO_AUDIO_OUT "no-audio-out" ///< No audio output port: nothing to read.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NO_AUDIO_OUT. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NO_AUDIO_OUT_TEXT_EN "No audio output port: nothing to read."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_SILENT_OUTPUT "silent-output" ///< Driven, and silent under a stimulus that should have passed.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_SILENT_OUTPUT. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_SILENT_OUTPUT_TEXT_EN "Driven, and silent under a stimulus that should have passed."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_CARRIER "needs-carrier" ///< Needs a second audio input the prober did not supply.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_CARRIER. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_CARRIER_TEXT_EN "Needs a second audio input the prober did not supply."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_IMPULSE_RESPONSE "needs-impulse-response" ///< A convolver needing an impulse response the prober did not load.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_IMPULSE_RESPONSE. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_IMPULSE_RESPONSE_TEXT_EN "A convolver needing an impulse response the prober did not load."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_CONTENT "needs-content" ///< An instrument that is silent under notes until a sample, a sound font or an instrument file is loaded, which the prober did not load.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_CONTENT. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NEEDS_CONTENT_TEXT_EN "An instrument that is silent under notes until a sample, a sound font or an instrument file is loaded, which the prober did not load."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_UNPINNABLE "unpinnable" ///< The files the host loads cannot be pinned.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_UNPINNABLE. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_UNPINNABLE_TEXT_EN "The files the host loads cannot be pinned."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NO_VOICES "no-voices" ///< An instrument whose voice-info declares a capacity of 0.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NO_VOICES. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NO_VOICES_TEXT_EN "An instrument whose voice-info declares a capacity of 0."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NOTES_UNPLAYABLE "notes-unplayable" ///< An instrument whose note input reads no dialect the prober speaks.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NOTES_UNPLAYABLE. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NOTES_UNPLAYABLE_TEXT_EN "An instrument whose note input reads no dialect the prober speaks."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_VOICES_UNKNOWN "voices-unknown" ///< An instrument that declares no voice capacity, run with no probe count.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_VOICES_UNKNOWN. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_VOICES_UNKNOWN_TEXT_EN "An instrument that declares no voice capacity, run with no probe count."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_REFUSED_INSTANTIATION "refused-instantiation" ///< The plugin would not instantiate at this rate or block size.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_REFUSED_INSTANTIATION. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_REFUSED_INSTANTIATION_TEXT_EN "The plugin would not instantiate at this rate or block size."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_CRASHED "probe-crashed" ///< The probe worker died while hosting the plugin.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_CRASHED. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_CRASHED_TEXT_EN "The probe worker died while hosting the plugin."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_TIMEOUT "probe-timeout" ///< The probe passed its per-plugin time limit.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_TIMEOUT. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_TIMEOUT_TEXT_EN "The probe passed its per-plugin time limit."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NON_FINITE_OUTPUT "non-finite-output" ///< The output held NaN or infinity.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NON_FINITE_OUTPUT. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NON_FINITE_OUTPUT_TEXT_EN "The output held NaN or infinity."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NOT_INSTALLED "not-installed" ///< The plugin is not installed on this machine.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NOT_INSTALLED. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NOT_INSTALLED_TEXT_EN "The plugin is not installed on this machine."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_WORKER_NONCONFORMING "worker-nonconforming" ///< An LV2 worker interface with work or work_response NULL.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_WORKER_NONCONFORMING. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_WORKER_NONCONFORMING_TEXT_EN "An LV2 worker interface with work or work_response NULL."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_ERROR "probe-error" ///< A failure with no more specific reason; its own words are kept beside it.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_ERROR. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_PROBE_ERROR_TEXT_EN "A failure with no more specific reason; its own words are kept beside it."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NOT_ATTEMPTED "not-attempted" ///< The run did not cover this plugin for this dimension.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_NOT_ATTEMPTED. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_NOT_ATTEMPTED_TEXT_EN "The run did not cover this plugin for this dimension."
#define OMX_MEASUREMENT_UNMEASURED_REASONS_MEMORY_BOUND "memory-bound" ///< A measurement pass did not fit the memory bound the run set: that pass alone is unmeasured, and the passes after it are measured.
/** The source sentence (English) of OMX_MEASUREMENT_UNMEASURED_REASONS_MEMORY_BOUND. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_MEMORY_BOUND_TEXT_EN "A measurement pass did not fit the memory bound the run set: that pass alone is unmeasured, and the passes after it are measured."
/** The number of words of MEASUREMENT_UNMEASURED_REASONS. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_COUNT 19u
/** The words of MEASUREMENT_UNMEASURED_REASONS in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS_INIT { "no-audio-in", "no-audio-out", "silent-output", "needs-carrier", "needs-impulse-response", "needs-content", "unpinnable", "no-voices", "notes-unplayable", "voices-unknown", "refused-instantiation", "probe-crashed", "probe-timeout", "non-finite-output", "not-installed", "worker-nonconforming", "probe-error", "not-attempted", "memory-bound" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_UNMEASURED_REASONS, in order, the code being its place in the order. Every reason a figure may be absent, each of its kind: an outcome a sweep produced, never a hypothetical. A reader that meets a reason it does not know treats it as probe-failed. */
#define OMX_MEASUREMENT_UNMEASURED_REASONS(X) \
    X(0u, "no-audio-in", NO_AUDIO_IN) X(1u, "no-audio-out", NO_AUDIO_OUT) X(2u, "silent-output", SILENT_OUTPUT) X(3u, "needs-carrier", NEEDS_CARRIER) \
    X(4u, "needs-impulse-response", NEEDS_IMPULSE_RESPONSE) X(5u, "needs-content", NEEDS_CONTENT) X(6u, "unpinnable", UNPINNABLE) X(7u, "no-voices", NO_VOICES) \
    X(8u, "notes-unplayable", NOTES_UNPLAYABLE) X(9u, "voices-unknown", VOICES_UNKNOWN) X(10u, "refused-instantiation", REFUSED_INSTANTIATION) X(11u, "probe-crashed", PROBE_CRASHED) \
    X(12u, "probe-timeout", PROBE_TIMEOUT) X(13u, "non-finite-output", NON_FINITE_OUTPUT) X(14u, "not-installed", NOT_INSTALLED) X(15u, "worker-nonconforming", WORKER_NONCONFORMING) \
    X(16u, "probe-error", PROBE_ERROR) X(17u, "not-attempted", NOT_ATTEMPTED) X(18u, "memory-bound", MEMORY_BOUND)

/* MEASUREMENT_LATENCY_METHODS (qualification/qualification.json) */
#define OMX_MEASUREMENT_LATENCY_METHODS_IMPULSE_ONSET "impulse-onset" ///< The delay from a unit impulse to the first output sample above the residual floor: what the plugin does.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_METHODS_IMPULSE_ONSET. */
#define OMX_MEASUREMENT_LATENCY_METHODS_IMPULSE_ONSET_TEXT_EN "The delay from a unit impulse to the first output sample above the residual floor: what the plugin does."
#define OMX_MEASUREMENT_LATENCY_METHODS_DECLARED_PORT "declared-port" ///< Read from the plugin's own latency report: what it claims.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_METHODS_DECLARED_PORT. */
#define OMX_MEASUREMENT_LATENCY_METHODS_DECLARED_PORT_TEXT_EN "Read from the plugin's own latency report: what it claims."
#define OMX_MEASUREMENT_LATENCY_METHODS_NOTE_ONSET "note-onset" ///< The delay from a note on to the first output sample above the floor.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_METHODS_NOTE_ONSET. */
#define OMX_MEASUREMENT_LATENCY_METHODS_NOTE_ONSET_TEXT_EN "The delay from a note on to the first output sample above the floor."
/** The number of words of MEASUREMENT_LATENCY_METHODS. */
#define OMX_MEASUREMENT_LATENCY_METHODS_COUNT 3u
/** The words of MEASUREMENT_LATENCY_METHODS in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_LATENCY_METHODS_INIT { "impulse-onset", "declared-port", "note-onset" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_LATENCY_METHODS, in order, the code being its place in the order. How a latency figure was taken. note-onset is an instrument's: a held note's first sound. */
#define OMX_MEASUREMENT_LATENCY_METHODS(X) \
    X(0u, "impulse-onset", IMPULSE_ONSET) X(1u, "declared-port", DECLARED_PORT) X(2u, "note-onset", NOTE_ONSET)

/* MEASUREMENT_COST_METHODS (qualification/qualification.json) */
#define OMX_MEASUREMENT_COST_METHODS_BLOCK_TIME_PERCENTILE "block-time-percentile" ///< A percentile of per-block wall time under a sustained stimulus, warm-up discarded, in nanoseconds per sample.
/** The source sentence (English) of OMX_MEASUREMENT_COST_METHODS_BLOCK_TIME_PERCENTILE. */
#define OMX_MEASUREMENT_COST_METHODS_BLOCK_TIME_PERCENTILE_TEXT_EN "A percentile of per-block wall time under a sustained stimulus, warm-up discarded, in nanoseconds per sample."
/** The number of words of MEASUREMENT_COST_METHODS. */
#define OMX_MEASUREMENT_COST_METHODS_COUNT 1u
/** The words of MEASUREMENT_COST_METHODS in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_COST_METHODS_INIT { "block-time-percentile" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_COST_METHODS, in order, the code being its place in the order. How a cost figure was taken. */
#define OMX_MEASUREMENT_COST_METHODS(X) \
    X(0u, "block-time-percentile", BLOCK_TIME_PERCENTILE)

/* MEASUREMENT_LATENCY_SCALING (qualification/qualification.json) */
#define OMX_MEASUREMENT_LATENCY_SCALING_FIXED_FRAME "fixed-frame" ///< The same frame count at every rate.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_FIXED_FRAME. */
#define OMX_MEASUREMENT_LATENCY_SCALING_FIXED_FRAME_TEXT_EN "The same frame count at every rate."
#define OMX_MEASUREMENT_LATENCY_SCALING_FIXED_TIME "fixed-time" ///< The same milliseconds at every rate.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_FIXED_TIME. */
#define OMX_MEASUREMENT_LATENCY_SCALING_FIXED_TIME_TEXT_EN "The same milliseconds at every rate."
#define OMX_MEASUREMENT_LATENCY_SCALING_ZERO "zero" ///< No latency a mix can notice at any measured rate.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_ZERO. */
#define OMX_MEASUREMENT_LATENCY_SCALING_ZERO_TEXT_EN "No latency a mix can notice at any measured rate."
#define OMX_MEASUREMENT_LATENCY_SCALING_NONCONFORMING "nonconforming" ///< Fits neither law at a magnitude that reaches a mix: flagged, never averaged.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_NONCONFORMING. */
#define OMX_MEASUREMENT_LATENCY_SCALING_NONCONFORMING_TEXT_EN "Fits neither law at a magnitude that reaches a mix: flagged, never averaged."
#define OMX_MEASUREMENT_LATENCY_SCALING_SINGLE_RATE "single-rate" ///< One usable reading: no law can be fitted.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_SINGLE_RATE. */
#define OMX_MEASUREMENT_LATENCY_SCALING_SINGLE_RATE_TEXT_EN "One usable reading: no law can be fitted."
#define OMX_MEASUREMENT_LATENCY_SCALING_UNMEASURED "unmeasured" ///< No rate produced a figure.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_UNMEASURED. */
#define OMX_MEASUREMENT_LATENCY_SCALING_UNMEASURED_TEXT_EN "No rate produced a figure."
/** The number of words of MEASUREMENT_LATENCY_SCALING. */
#define OMX_MEASUREMENT_LATENCY_SCALING_COUNT 6u
/** The words of MEASUREMENT_LATENCY_SCALING in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_LATENCY_SCALING_INIT { "fixed-frame", "fixed-time", "zero", "nonconforming", "single-rate", "unmeasured" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_LATENCY_SCALING, in order, the code being its place in the order. How latency moves with the sample rate, derived from readings at several rates, never assumed from a plugin's name. */
#define OMX_MEASUREMENT_LATENCY_SCALING(X) \
    X(0u, "fixed-frame", FIXED_FRAME) X(1u, "fixed-time", FIXED_TIME) X(2u, "zero", ZERO) X(3u, "nonconforming", NONCONFORMING) \
    X(4u, "single-rate", SINGLE_RATE) X(5u, "unmeasured", UNMEASURED)

/* MEASUREMENT_LATENCY_SCALING_NOTES (qualification/qualification.json) */
#define OMX_MEASUREMENT_LATENCY_SCALING_NOTES_BELOW_BUDGET "below-budget" ///< The readings fit no law but every one is inside the latency budget: the detector's noise.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_NOTES_BELOW_BUDGET. */
#define OMX_MEASUREMENT_LATENCY_SCALING_NOTES_BELOW_BUDGET_TEXT_EN "The readings fit no law but every one is inside the latency budget: the detector's noise."
#define OMX_MEASUREMENT_LATENCY_SCALING_NOTES_INFORMATIONAL_RATE "informational-rate" ///< Only a reading below the operational rates breaks the law; it stays as information.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_SCALING_NOTES_INFORMATIONAL_RATE. */
#define OMX_MEASUREMENT_LATENCY_SCALING_NOTES_INFORMATIONAL_RATE_TEXT_EN "Only a reading below the operational rates breaks the law; it stays as information."
/** The number of words of MEASUREMENT_LATENCY_SCALING_NOTES. */
#define OMX_MEASUREMENT_LATENCY_SCALING_NOTES_COUNT 2u
/** The words of MEASUREMENT_LATENCY_SCALING_NOTES in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_LATENCY_SCALING_NOTES_INIT { "below-budget", "informational-rate" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_LATENCY_SCALING_NOTES, in order, the code being its place in the order. Why a derived scaling class is not the naive fit over every reading. */
#define OMX_MEASUREMENT_LATENCY_SCALING_NOTES(X) \
    X(0u, "below-budget", BELOW_BUDGET) X(1u, "informational-rate", INFORMATIONAL_RATE)

/* MEASUREMENT_LATENCY_EXCLUSIONS (qualification/qualification.json) */
#define OMX_MEASUREMENT_LATENCY_EXCLUSIONS_IMPOSSIBLE_ZERO "impossible-zero" ///< Zero frames at this rate while another rate measured non-zero.
/** The source sentence (English) of OMX_MEASUREMENT_LATENCY_EXCLUSIONS_IMPOSSIBLE_ZERO. */
#define OMX_MEASUREMENT_LATENCY_EXCLUSIONS_IMPOSSIBLE_ZERO_TEXT_EN "Zero frames at this rate while another rate measured non-zero."
/** The number of words of MEASUREMENT_LATENCY_EXCLUSIONS. */
#define OMX_MEASUREMENT_LATENCY_EXCLUSIONS_COUNT 1u
/** The words of MEASUREMENT_LATENCY_EXCLUSIONS in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_LATENCY_EXCLUSIONS_INIT { "impossible-zero" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_LATENCY_EXCLUSIONS, in order, the code being its place in the order. Why one rate's reading was left out of the fit and of every rate resolution. */
#define OMX_MEASUREMENT_LATENCY_EXCLUSIONS(X) \
    X(0u, "impossible-zero", IMPOSSIBLE_ZERO)

/* MEASUREMENT_VOICE_BASES (qualification/qualification.json) */
#define OMX_MEASUREMENT_VOICE_BASES_DECLARED "declared"
/** The source sentence (English) of OMX_MEASUREMENT_VOICE_BASES_DECLARED. */
#define OMX_MEASUREMENT_VOICE_BASES_DECLARED_TEXT_EN "The voice capacity the plugin declares through CLAP's voice-info extension."
#define OMX_MEASUREMENT_VOICE_BASES_PROBE "probe"
/** The source sentence (English) of OMX_MEASUREMENT_VOICE_BASES_PROBE. */
#define OMX_MEASUREMENT_VOICE_BASES_PROBE_TEXT_EN "A note count the caller gave the prober, not read from the plugin."
/** The number of words of MEASUREMENT_VOICE_BASES. */
#define OMX_MEASUREMENT_VOICE_BASES_COUNT 2u
/** The words of MEASUREMENT_VOICE_BASES in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_VOICE_BASES_INIT { "declared", "probe" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_VOICE_BASES, in order, the code being its place in the order. Where the number of notes an instrument's cost was measured with came from: the voice capacity the plugin declares (CLAP voice-info), or a count the caller gave. */
#define OMX_MEASUREMENT_VOICE_BASES(X) \
    X(0u, "declared", DECLARED) X(1u, "probe", PROBE)

/* MEASUREMENT_VERDICT_RATINGS (qualification/qualification.json) */
#define OMX_MEASUREMENT_VERDICT_RATINGS_SUITABLE "suitable"
/** The source sentence (English) of OMX_MEASUREMENT_VERDICT_RATINGS_SUITABLE. */
#define OMX_MEASUREMENT_VERDICT_RATINGS_SUITABLE_TEXT_EN "The plugin meets the host profile's budget on every measured dimension."
#define OMX_MEASUREMENT_VERDICT_RATINGS_CONDITIONAL "conditional"
/** The source sentence (English) of OMX_MEASUREMENT_VERDICT_RATINGS_CONDITIONAL. */
#define OMX_MEASUREMENT_VERDICT_RATINGS_CONDITIONAL_TEXT_EN "The plugin meets the host profile's budget only under a stated condition."
#define OMX_MEASUREMENT_VERDICT_RATINGS_UNKNOWN "unknown"
/** The source sentence (English) of OMX_MEASUREMENT_VERDICT_RATINGS_UNKNOWN. */
#define OMX_MEASUREMENT_VERDICT_RATINGS_UNKNOWN_TEXT_EN "Not enough was measured to rate the plugin against the host profile."
#define OMX_MEASUREMENT_VERDICT_RATINGS_UNSUITABLE "unsuitable"
/** The source sentence (English) of OMX_MEASUREMENT_VERDICT_RATINGS_UNSUITABLE. */
#define OMX_MEASUREMENT_VERDICT_RATINGS_UNSUITABLE_TEXT_EN "The plugin does not meet the host profile's budget on at least one measured dimension."
/** The number of words of MEASUREMENT_VERDICT_RATINGS. */
#define OMX_MEASUREMENT_VERDICT_RATINGS_COUNT 4u
/** The words of MEASUREMENT_VERDICT_RATINGS in their declared order, as a C initializer list. */
#define OMX_MEASUREMENT_VERDICT_RATINGS_INIT { "suitable", "conditional", "unknown", "unsuitable" }
/** Expands `X(code, "word", NAME)` once per word of MEASUREMENT_VERDICT_RATINGS, in order, the code being its place in the order. The four ratings a verdict speaks, in order from the best. */
#define OMX_MEASUREMENT_VERDICT_RATINGS(X) \
    X(0u, "suitable", SUITABLE) X(1u, "conditional", CONDITIONAL) X(2u, "unknown", UNKNOWN) X(3u, "unsuitable", UNSUITABLE)

/* RESOURCE_MEMORY_PHASES (qualification/qualification.json) */
#define OMX_RESOURCE_MEMORY_PHASES_AFTER_INSTANTIATE "after-instantiate"
/** The source sentence (English) of OMX_RESOURCE_MEMORY_PHASES_AFTER_INSTANTIATE. */
#define OMX_RESOURCE_MEMORY_PHASES_AFTER_INSTANTIATE_TEXT_EN "Memory read right after the plugin instantiates."
#define OMX_RESOURCE_MEMORY_PHASES_AFTER_ACTIVATE "after-activate"
/** The source sentence (English) of OMX_RESOURCE_MEMORY_PHASES_AFTER_ACTIVATE. */
#define OMX_RESOURCE_MEMORY_PHASES_AFTER_ACTIVATE_TEXT_EN "Memory read right after the plugin activates."
#define OMX_RESOURCE_MEMORY_PHASES_AT_REST "at-rest"
/** The source sentence (English) of OMX_RESOURCE_MEMORY_PHASES_AT_REST. */
#define OMX_RESOURCE_MEMORY_PHASES_AT_REST_TEXT_EN "Memory read at rest, after processing, with no note playing."
#define OMX_RESOURCE_MEMORY_PHASES_NOTES_HELD "notes-held"
/** The source sentence (English) of OMX_RESOURCE_MEMORY_PHASES_NOTES_HELD. */
#define OMX_RESOURCE_MEMORY_PHASES_NOTES_HELD_TEXT_EN "Memory read while notes are held."
#define OMX_RESOURCE_MEMORY_PHASES_SECOND_INSTANCE "second-instance"
/** The source sentence (English) of OMX_RESOURCE_MEMORY_PHASES_SECOND_INSTANCE. */
#define OMX_RESOURCE_MEMORY_PHASES_SECOND_INSTANCE_TEXT_EN "Memory read for a second instance, so a shared one-time load is told apart from the per-instance cost."
/** The number of words of RESOURCE_MEMORY_PHASES. */
#define OMX_RESOURCE_MEMORY_PHASES_COUNT 5u
/** The words of RESOURCE_MEMORY_PHASES in their declared order, as a C initializer list. */
#define OMX_RESOURCE_MEMORY_PHASES_INIT { "after-instantiate", "after-activate", "at-rest", "notes-held", "second-instance" }
/** Expands `X(code, "word", NAME)` once per word of RESOURCE_MEMORY_PHASES, in order, the code being its place in the order. When a plugin's memory is read, per instance (plugin-qualify#114): after instantiate, after activate, at rest after processing, with notes held, and for a second instance, so a shared one-time load is told apart from the per-instance cost. */
#define OMX_RESOURCE_MEMORY_PHASES(X) \
    X(0u, "after-instantiate", AFTER_INSTANTIATE) X(1u, "after-activate", AFTER_ACTIVATE) X(2u, "at-rest", AT_REST) X(3u, "notes-held", NOTES_HELD) \
    X(4u, "second-instance", SECOND_INSTANCE)

/* RESOURCE_UNMEASURED_REASONS (qualification/qualification.json) */
#define OMX_RESOURCE_UNMEASURED_REASONS_UNMEASURED_ON_CLASS "unmeasured-on-class" ///< The only figure was taken on another machine class: never read as a pass, never scaled.
/** The source sentence (English) of OMX_RESOURCE_UNMEASURED_REASONS_UNMEASURED_ON_CLASS. */
#define OMX_RESOURCE_UNMEASURED_REASONS_UNMEASURED_ON_CLASS_TEXT_EN "The only figure was taken on another machine class: never read as a pass, never scaled."
#define OMX_RESOURCE_UNMEASURED_REASONS_LIMIT_EXCEEDED "limit-exceeded" ///< The run hit the limit probe isolation set for the resource; the limit is recorded beside it.
/** The source sentence (English) of OMX_RESOURCE_UNMEASURED_REASONS_LIMIT_EXCEEDED. */
#define OMX_RESOURCE_UNMEASURED_REASONS_LIMIT_EXCEEDED_TEXT_EN "The run hit the limit probe isolation set for the resource; the limit is recorded beside it."
/** The number of words of RESOURCE_UNMEASURED_REASONS. */
#define OMX_RESOURCE_UNMEASURED_REASONS_COUNT 2u
/** The words of RESOURCE_UNMEASURED_REASONS in their declared order, as a C initializer list. */
#define OMX_RESOURCE_UNMEASURED_REASONS_INIT { "unmeasured-on-class", "limit-exceeded" }
/** Expands `X(code, "word", NAME)` once per word of RESOURCE_UNMEASURED_REASONS, in order, the code being its place in the order. Why a resource has no figure a host profile can read, beside the measurement's own reasons (MEASUREMENT_UNMEASURED_REASONS). */
#define OMX_RESOURCE_UNMEASURED_REASONS(X) \
    X(0u, "unmeasured-on-class", UNMEASURED_ON_CLASS) X(1u, "limit-exceeded", LIMIT_EXCEEDED)

/* RESOURCE_BUDGET_SCOPES (qualification/qualification.json) */
#define OMX_RESOURCE_BUDGET_SCOPES_PER_INSTANCE "per-instance"
/** The source sentence (English) of OMX_RESOURCE_BUDGET_SCOPES_PER_INSTANCE. */
#define OMX_RESOURCE_BUDGET_SCOPES_PER_INSTANCE_TEXT_EN "Counted over one plugin instance."
#define OMX_RESOURCE_BUDGET_SCOPES_PER_CONSOLE "per-console"
/** The source sentence (English) of OMX_RESOURCE_BUDGET_SCOPES_PER_CONSOLE. */
#define OMX_RESOURCE_BUDGET_SCOPES_PER_CONSOLE_TEXT_EN "Counted over the whole console."
/** The number of words of RESOURCE_BUDGET_SCOPES. */
#define OMX_RESOURCE_BUDGET_SCOPES_COUNT 2u
/** The words of RESOURCE_BUDGET_SCOPES in their declared order, as a C initializer list. */
#define OMX_RESOURCE_BUDGET_SCOPES_INIT { "per-instance", "per-console" }
/** Expands `X(code, "word", NAME)` once per word of RESOURCE_BUDGET_SCOPES, in order, the code being its place in the order. What a host profile's budget for a resource is counted over (plugin-qualify#114, #115): one plugin instance, or the whole console. */
#define OMX_RESOURCE_BUDGET_SCOPES(X) \
    X(0u, "per-instance", PER_INSTANCE) X(1u, "per-console", PER_CONSOLE)

/* RESOURCE_HOST_ISOLATIONS (qualification/qualification.json) */
#define OMX_RESOURCE_HOST_ISOLATIONS_IN_PROCESS "in-process"
/** The source sentence (English) of OMX_RESOURCE_HOST_ISOLATIONS_IN_PROCESS. */
#define OMX_RESOURCE_HOST_ISOLATIONS_IN_PROCESS_TEXT_EN "The host runs its plugins in its own process."
#define OMX_RESOURCE_HOST_ISOLATIONS_PER_PROCESS "per-process"
/** The source sentence (English) of OMX_RESOURCE_HOST_ISOLATIONS_PER_PROCESS. */
#define OMX_RESOURCE_HOST_ISOLATIONS_PER_PROCESS_TEXT_EN "The host runs each plugin in its own process."
#define OMX_RESOURCE_HOST_ISOLATIONS_SHARED_PROCESS "shared-process"
/** The source sentence (English) of OMX_RESOURCE_HOST_ISOLATIONS_SHARED_PROCESS. */
#define OMX_RESOURCE_HOST_ISOLATIONS_SHARED_PROCESS_TEXT_EN "The host runs its plugins together in one process apart from its own."
/** The number of words of RESOURCE_HOST_ISOLATIONS. */
#define OMX_RESOURCE_HOST_ISOLATIONS_COUNT 3u
/** The words of RESOURCE_HOST_ISOLATIONS in their declared order, as a C initializer list. */
#define OMX_RESOURCE_HOST_ISOLATIONS_INIT { "in-process", "per-process", "shared-process" }
/** Expands `X(code, "word", NAME)` once per word of RESOURCE_HOST_ISOLATIONS, in order, the code being its place in the order. How a host runs its plugins. */
#define OMX_RESOURCE_HOST_ISOLATIONS(X) \
    X(0u, "in-process", IN_PROCESS) X(1u, "per-process", PER_PROCESS) X(2u, "shared-process", SHARED_PROCESS)

/* RESOURCE_HOST_LATENCY_HANDLING (qualification/qualification.json) */
#define OMX_RESOURCE_HOST_LATENCY_HANDLING_COMPENSATED "compensated"
/** The source sentence (English) of OMX_RESOURCE_HOST_LATENCY_HANDLING_COMPENSATED. */
#define OMX_RESOURCE_HOST_LATENCY_HANDLING_COMPENSATED_TEXT_EN "The host delays every other path to align on this plugin's reported latency."
#define OMX_RESOURCE_HOST_LATENCY_HANDLING_UNCOMPENSATED "uncompensated"
/** The source sentence (English) of OMX_RESOURCE_HOST_LATENCY_HANDLING_UNCOMPENSATED. */
#define OMX_RESOURCE_HOST_LATENCY_HANDLING_UNCOMPENSATED_TEXT_EN "The host passes the plugin's reported latency on, without aligning other paths to it."
/** The number of words of RESOURCE_HOST_LATENCY_HANDLING. */
#define OMX_RESOURCE_HOST_LATENCY_HANDLING_COUNT 2u
/** The words of RESOURCE_HOST_LATENCY_HANDLING in their declared order, as a C initializer list. */
#define OMX_RESOURCE_HOST_LATENCY_HANDLING_INIT { "compensated", "uncompensated" }
/** Expands `X(code, "word", NAME)` once per word of RESOURCE_HOST_LATENCY_HANDLING, in order, the code being its place in the order. Whether a host aligns on a plugin's reported latency or only passes it on. */
#define OMX_RESOURCE_HOST_LATENCY_HANDLING(X) \
    X(0u, "compensated", COMPENSATED) X(1u, "uncompensated", UNCOMPENSATED)

/* RESOURCE_THREAD_SCHEDULING (qualification/qualification.json) */
#define OMX_RESOURCE_THREAD_SCHEDULING_NONE "none"
/** The source sentence (English) of OMX_RESOURCE_THREAD_SCHEDULING_NONE. */
#define OMX_RESOURCE_THREAD_SCHEDULING_NONE_TEXT_EN "No particular scheduling class: the thread runs as any other."
#define OMX_RESOURCE_THREAD_SCHEDULING_FIFO "fifo"
/** The source sentence (English) of OMX_RESOURCE_THREAD_SCHEDULING_FIFO. */
#define OMX_RESOURCE_THREAD_SCHEDULING_FIFO_TEXT_EN "The real-time FIFO scheduling class."
/** The number of words of RESOURCE_THREAD_SCHEDULING. */
#define OMX_RESOURCE_THREAD_SCHEDULING_COUNT 2u
/** The words of RESOURCE_THREAD_SCHEDULING in their declared order, as a C initializer list. */
#define OMX_RESOURCE_THREAD_SCHEDULING_INIT { "none", "fifo" }
/** Expands `X(code, "word", NAME)` once per word of RESOURCE_THREAD_SCHEDULING, in order, the code being its place in the order. The scheduling class a host gives its plugin's threads, as the probe output records it. */
#define OMX_RESOURCE_THREAD_SCHEDULING(X) \
    X(0u, "none", NONE) X(1u, "fifo", FIFO)

/* MACHINE_CLASSES (qualification/qualification.json) */
#define OMX_MACHINE_CLASSES_DESK "desk" ///< An x86-64 desk.
/** The source sentence (English) of OMX_MACHINE_CLASSES_DESK. */
#define OMX_MACHINE_CLASSES_DESK_TEXT_EN "An x86-64 desk."
#define OMX_MACHINE_CLASSES_RASPBERRY_PI4 "raspberry-pi-4" ///< A Raspberry Pi 4, aarch64.
/** The source sentence (English) of OMX_MACHINE_CLASSES_RASPBERRY_PI4. */
#define OMX_MACHINE_CLASSES_RASPBERRY_PI4_TEXT_EN "A Raspberry Pi 4, aarch64."
#define OMX_MACHINE_CLASSES_RASPBERRY_PI5 "raspberry-pi-5" ///< A Raspberry Pi 5, aarch64.
/** The source sentence (English) of OMX_MACHINE_CLASSES_RASPBERRY_PI5. */
#define OMX_MACHINE_CLASSES_RASPBERRY_PI5_TEXT_EN "A Raspberry Pi 5, aarch64."
/** The number of words of MACHINE_CLASSES. */
#define OMX_MACHINE_CLASSES_COUNT 3u
/** The words of MACHINE_CLASSES in their declared order, as a C initializer list. */
#define OMX_MACHINE_CLASSES_INIT { "desk", "raspberry-pi-4", "raspberry-pi-5" }
/** Expands `X(code, "word", NAME)` once per word of MACHINE_CLASSES, in order, the code being its place in the order. The machine classes a host profile budgets for (plugin-qualify#114, #115): the desk, and the Raspberry Pi 4 and 5 a small console runs on. */
#define OMX_MACHINE_CLASSES(X) \
    X(0u, "desk", DESK) X(1u, "raspberry-pi-4", RASPBERRY_PI4) X(2u, "raspberry-pi-5", RASPBERRY_PI5)

#endif /* QUALIFICATION_VOCABULARY_H */
