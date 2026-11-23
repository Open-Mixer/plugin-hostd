/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/** @file transforms.h
 * @brief The transforms a format table names (docs/formats.md): a closed list of functions and their inverses.
 *
 * Each transform is a function from a field's text in a scan to a descriptor word's value (inbound) and its inverse.
 * A table refers to one by name and gives its data (the values of a lookup, the factor of a scale-by); it never
 * defines one. A new transform is added when a row needs it. A value crosses as text: the dump's text on the format
 * side, a JSON literal on the descriptor side. The transforms keep no state: each reads its arguments and the constant
 * list, and may be called from any thread.
 */

#ifndef PLUGIN_HOSTD_TRANSFORMS_H
#define PLUGIN_HOSTD_TRANSFORMS_H

#include <stddef.h>

/** @brief The answer of a transform that wrote its result in out. */
#define TRANSFORMS_OK 0
/** @brief The answer of a transform whose value gives nothing: a lookup with no entry for it, a flag that is false. */
#define TRANSFORMS_NONE 1
/** @brief The answer of a transform that cannot read the value, or whose out is too small. */
#define TRANSFORMS_REFUSED (-1)

/** @brief The data a table's row gives its transform. */
typedef struct
{
    const char *key;            /**< the row's key: what the inverse of flag writes */
    const char *const *from;    /**< a lookup's values on the format side, n of them */
    const char *const *to;      /**< a lookup's values on the descriptor side, as JSON literals, n of them */
    size_t n;                   /**< the number of values in from and in to */
    double factor;              /**< the factor of a scale-by */
} transforms_data_t;

/**
 * @brief A transform, inbound or inverse: a function from one value's text to the other side's text.
 *
 * @param d the row's data
 * @param in the value, as text
 * @param[out] out the result, NUL-terminated
 * @param size the room in out
 * @return TRANSFORMS_OK with the result in out, TRANSFORMS_NONE or TRANSFORMS_REFUSED
 */
typedef int (*transforms_fn_t)(const transforms_data_t *d, const char *in, char *out, size_t size);

/**
 * @brief The closed list of the transforms, as rows X(name, inbound, inverse).
 *
 * @param X the macro each row is handed to: the name a table writes, the inbound function and its inverse
 */
#define TRANSFORMS(X)                                                                                                  \
    X("identity", transforms_identity, transforms_identity_inverse)                                                    \
    X("lookup", transforms_lookup, transforms_lookup_inverse)                                                          \
    X("scale-by", transforms_scale_by, transforms_scale_by_inverse)                                                    \
    X("flag", transforms_flag, transforms_flag_inverse)                                                                \
    X("scale-points", transforms_scale_points, transforms_scale_points_inverse)                                        \
    X("group-path", transforms_group_path, transforms_group_path_inverse)                                              \
    X("port-group", transforms_port_group, transforms_port_group_inverse)                                              \
    X("output-symbol", transforms_output_symbol, transforms_output_symbol_inverse)                                     \
    X("role-to-meaning", transforms_role_to_meaning, transforms_role_to_meaning_inverse)

/**
 * @brief The declarations of the two functions of one row of TRANSFORMS, each of the type transforms_fn_t.
 *
 * @param name the transform's name (unused here)
 * @param in the inbound function
 * @param inverse its inverse
 */
#define TRANSFORMS_DECLARE(name, in, inverse)                                                                          \
    int in(const transforms_data_t *d, const char *value, char *out, size_t size);                                     \
    int inverse(const transforms_data_t *d, const char *value, char *out, size_t size);
TRANSFORMS(TRANSFORMS_DECLARE)
#undef TRANSFORMS_DECLARE

/** @brief One transform of the list: its name and its two functions. */
typedef struct
{
    const char *name;           /**< the name a table refers to it by */
    transforms_fn_t inbound;    /**< from the format side to the descriptor side */
    transforms_fn_t inverse;    /**< from the descriptor side back to the format side */
} transforms_entry_t;

/** @brief The list of the transforms, in TRANSFORMS(X) order. */
extern const transforms_entry_t transforms_list[];
/** @brief The number of entries of transforms_list. */
extern const size_t transforms_count;

/**
 * @brief The transform of a name.
 *
 * @param name the name
 * @return the entry of transforms_list, or NULL when no transform has that name
 * @pre name is not NULL.
 */
const transforms_entry_t *transforms_find(const char *name);

/**
 * @brief Whether a lookup's values are one to one: no value of from and no value of to twice.
 *
 * A table with a lookup that is not is refused, since its inverse would have to choose.
 *
 * @param d the lookup's data
 * @return 0 when they are one to one, -1 otherwise
 * @pre d is not NULL; from and to each hold n strings.
 */
int transforms_lookup_check(const transforms_data_t *d);

#endif
