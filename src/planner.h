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

/** @file planner.h
 * @brief The grouping planner: given plugins in signal order, which runs of consecutive ones may share a worker.
 *
 * The grouping-planner design note, The planner. Every function here is pure and keeps no state: the same members and
 * settings give the same plan, byte for byte; it reads no clock, no file, no pin store and no global, and allocates
 * nothing, so it may be called from any thread. What it is given is gathered by the supervisor (src/supervisor.c),
 * what it answers is applied there.
 */

#ifndef PLANNER_H
#define PLANNER_H

#include <stddef.h>

/** @brief The most members of one plan: the words of a plan line less the verb and the chain. */
#define PLANNER_MEMBERS_MAX 62

/** @brief The cost of a member nobody measured. */
#define PLANNER_COST_UNKNOWN (-1.0)

/** @brief What a member's pin says, as far as the rules read it. */
enum {
    PLANNER_PIN_NONE,           /**< no pin */
    PLANNER_PIN_NO_VERDICT,     /**< a pin without a verdict: one the daemon learned on first use */
    PLANNER_PIN_IN_PROCESS,     /**< a pin whose verdict lets the plugin share a worker */
    PLANNER_PIN_ISOLATED,       /**< a pin whose verdict keeps the plugin alone (verdict-isolated) */
    PLANNER_PIN_REFUSED         /**< a pin that refuses the plugin (refused) */
};

/**
 * @brief The reasons of a plan, in the order of PLUGIN_HOSTD_GROUPING_REASONS (contract.d/plugin-hostd/grouping).
 *
 * The test holds each to its word, which planner_reason_word gives.
 */
enum {
    PLANNER_REASON_NONE = -1,           /**< a member with nothing to say */
    PLANNER_REASON_REFUSED,             /**< alone: pins are required and its pin is PLANNER_PIN_REFUSED */
    PLANNER_REASON_NO_PIN,              /**< alone: pins are required, it has none and the mode is not first-use */
    PLANNER_REASON_NO_VERDICT,          /**< alone: under first-use it has no pin or a pin without a verdict */
    PLANNER_REASON_VERDICT_ISOLATED,    /**< alone: pins are required and its pin is PLANNER_PIN_ISOLATED */
    PLANNER_REASON_FORMAT_WORLD,        /**< alone: pins are required and its world_ok is 0 */
    PLANNER_REASON_HISTORY_CRASHED,     /**< alone: its history says crashed */
    PLANNER_REASON_HISTORY_XRUNS,       /**< alone: its history says raises_xruns */
    PLANNER_REASON_COST_OVER,           /**< alone: its known cost is above group_cost_max */
    PLANNER_REASON_FORMAT_MIXED,        /**< starts a segment: its class is not that of the segment before it */
    PLANNER_REASON_GROUP_FULL,          /**< starts a segment: the one before it holds group_max members */
    PLANNER_REASON_GROUP_COST,          /**< starts a segment: its cost would take the last past group_cost_max */
    PLANNER_REASON_COST_ASSUMED,        /**< shares a segment with a cost nobody measured, while grouping is on */
    PLANNER_REASON_NO_NEIGHBOUR,        /**< a segment of one that no rule above made */
    PLANNER_REASON_GROUPING_OFF,        /**< shares a segment while grouping is off */
    PLANNER_REASON_HISTORY_UNAVAILABLE, /**< the plan was made without the history, and no rule above spoke */
    PLANNER_REASON_PLAN_REFUSED,        /**< a refused plan: planner_format_reasons writes it, planner_plan never */
    PLANNER_REASON_COUNT                /**< the number of reasons */
};

/**
 * @brief What the history of a plugin on this host class comes to, for the rules that read it.
 *
 * The design note, The history record. The rules are history-crashed, history-xruns, and the cost of a member, which
 * is the larger of the qualified one and cpu_p95_solo. The supervisor fills it from src/history.c, whose rules
 * (history_crashed, history_raises_xruns) are the source of truth, and from the quarantine, which is a crash the
 * daemon has seen itself. A member's history is NULL when there is none, which is neutral: a plugin with none is
 * judged by its pin and its cost.
 */
typedef struct PLANNER_HISTORY_T {
    int crashed;                /**< a crash within history_keep_days, or a quarantine now */
    int raises_xruns;           /**< more xrun windows grouped than alone */
    double cpu_p95_solo;        /**< fraction of one core over the windows run alone, PLANNER_COST_UNKNOWN for none */
} planner_history_t;

/** @brief One member of a plan: what the rules read of one plugin instance. */
typedef struct PLANNER_MEMBER_T {
    int id;                     /**< the instance */
    /** two members share a segment only when their classes are equal strings: the worker program that runs chains in
     * one client, else the row alone; never NULL */
    const char *klass;
    int pin;                    /**< PLANNER_PIN_* */
    /** a world holding this plugin can be built for a shared worker, or none needs building */
    int world_ok;
    /** a fraction of one core at the daemon's rate and quantum, PLANNER_COST_UNKNOWN for none */
    double cost;
    const planner_history_t *history; /**< its history, NULL for none */
} planner_member_t;

/** @brief The settings a plan is made under. */
typedef struct PLANNER_SETTINGS_T {
    int require_pins;           /**< the pin rules are read only while this is set */
    int pins_first_use;         /**< pin_mode is first-use, else strict */
    /** off: the segments are the same, and a member that shares one says PLANNER_REASON_GROUPING_OFF */
    int grouping_on;
    int group_max;              /**< most members of a segment, 0 for no limit */
    double group_cost_max;      /**< most the costs of a segment add to, a fraction of one core, 0 for no limit */
    int history_unavailable;    /**< the history is blocked or off: the plan is made without it, and says so */
} planner_settings_t;

/** @brief A plan: the segments, consecutive runs of the members in the order given, and each member's reason. */
typedef struct PLANNER_PLAN_T {
    int nseg;                           /**< the number of segments */
    int seg_len[PLANNER_MEMBERS_MAX];   /**< seg_len[0..nseg) are the lengths of the segments */
    int reason[PLANNER_MEMBERS_MAX];    /**< reason[k] is the reason of member k, PLANNER_REASON_NONE for none */
} planner_plan_t;

/**
 * @brief Plans n members into segments.
 *
 * A member a rule leaves alone is a segment of one; the others join the segment before them while their class, the
 * group_max and the group_cost_max allow. In a segment a member of unknown cost counts as the median of the known
 * costs of the members before it in the segment (0 when none is known), and the first member of a segment as 0.
 *
 * @param s the settings
 * @param m the members, in signal order
 * @param n the number of members, 1 to PLANNER_MEMBERS_MAX
 * @param[out] out the plan, written on 0 only
 * @return 0, or -1 for a number of members outside that
 * @pre s, m and out are not NULL; m holds n members, each with a klass.
 */
int planner_plan(const planner_settings_t *s, const planner_member_t *m, int n, planner_plan_t *out);

/**
 * @brief The word of a reason: the one of the domain plugin-hostd/grouping.
 *
 * @param reason a PLANNER_REASON_* value
 * @return the word, a constant string; NULL for PLANNER_REASON_NONE, PLANNER_REASON_COUNT and any other value
 */
const char *planner_reason_word(int reason);

/**
 * @brief Writes the segments as plan and plan_get answer them.
 *
 * The members of a segment are joined by commas, the segments by semicolons: "1,2;3". The text is truncated to size
 * as snprintf does; a plan of no segment writes nothing, not even the NUL.
 *
 * @param m the members the plan was made of
 * @param p the plan
 * @param[out] buf the text
 * @param size the room in buf; with 0, buf is not written and may be NULL
 * @return the length the whole text needs, without the NUL
 * @pre m and p are not NULL; m holds as many members as the segments of p add to.
 */
size_t planner_format_segments(const planner_member_t *m, const planner_plan_t *p, char *buf, size_t size);

/**
 * @brief Writes the reasons as plan_get answers them.
 *
 * \<instance\>:\<reason word\> joined by commas for the members that have a reason, PHD_WORD_NONE when no member has
 * one. A refused plan (refused_code is not 0) gives every member \<instance\>:plan-refused:\<refused_code\>, the
 * word being that of PLANNER_REASON_PLAN_REFUSED. The text is truncated to size as snprintf does.
 *
 * @param m the members the plan was made of
 * @param p the plan
 * @param refused_code the code the plan was refused with, 0 for a plan that was not
 * @param[out] buf the text
 * @param size the room in buf; with 0, buf is not written and may be NULL
 * @return the length the whole text needs, without the NUL
 * @pre m and p are not NULL; m holds as many members as the segments of p add to; each reason of p is one
 *      planner_plan writes.
 */
size_t planner_format_reasons(const planner_member_t *m, const planner_plan_t *p, int refused_code, char *buf, size_t size);

#endif
