// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#ifndef OMX_MACHINE_CODES_H
#define OMX_MACHINE_CODES_H
/*
 * GENERATED: DO NOT EDIT BY HAND.
 * Produced by `omx-contract render --target c --package machine` from the domain machine: the codes of its items marked
 * "x-c-codes", one OMX_<ITEM>_<WORD> per word and an OMX_<ITEM>_COUNT per item, and an OMX_<ITEM>(X) X-macro where the
 * item is marked "x-c-xmacro" as well. Nothing else of the domain is rendered: its words are read at run time.
 */

/* MACHINE_CORE_BANDS */
#define OMX_MACHINE_CORE_BANDS_CORES1_TO2 0u
#define OMX_MACHINE_CORE_BANDS_CORES3_TO4 1u
#define OMX_MACHINE_CORE_BANDS_CORES5_TO8 2u
#define OMX_MACHINE_CORE_BANDS_CORES9_TO16 3u
#define OMX_MACHINE_CORE_BANDS_CORES17_TO32 4u
#define OMX_MACHINE_CORE_BANDS_CORES33_UP 5u
#define OMX_MACHINE_CORE_BANDS_COUNT 6u

/* MACHINE_CLOCK_BANDS */
#define OMX_MACHINE_CLOCK_BANDS_UNDER1500_MHZ 0u
#define OMX_MACHINE_CLOCK_BANDS_FROM1500_TO2500_MHZ 1u
#define OMX_MACHINE_CLOCK_BANDS_FROM2500_TO3500_MHZ 2u
#define OMX_MACHINE_CLOCK_BANDS_FROM3500_TO4500_MHZ 3u
#define OMX_MACHINE_CLOCK_BANDS_FROM4500_MHZ 4u
#define OMX_MACHINE_CLOCK_BANDS_COUNT 5u

/* MACHINE_FAMILIES */
#define OMX_MACHINE_FAMILIES_INTEL 0u
#define OMX_MACHINE_FAMILIES_AMD 1u
#define OMX_MACHINE_FAMILIES_ARM 2u
#define OMX_MACHINE_FAMILIES_UNKNOWN 3u
#define OMX_MACHINE_FAMILIES_COUNT 4u

#endif /* OMX_MACHINE_CODES_H */
