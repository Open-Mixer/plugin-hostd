/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/** @file json.h
 * @brief Strings that grow, and the lookups of the JSON the daemon's programs read.
 *
 * The probe runner writes its documents with the strings (json.c). The lookups are the ones every reader here makes of
 * a cJSON value (libcjson): the probe runner of its child's JSON, describe of the format tables. Each lookup takes
 * NULL, or a value of another type, for "not there". The functions keep no state of their own: each works on the
 * string or the value it is given.
 */

#ifndef PLUGIN_HOSTD_JSON_H
#define PLUGIN_HOSTD_JSON_H

#include <stddef.h>

#include <cjson/cJSON.h>

/** @brief A string that grows. */
typedef struct
{
    char *s;                    /**< the text, NUL-terminated, malloc'd; NULL until something is put */
    size_t len,                 /**< the bytes in s, without the NUL */
        cap;                    /**< the bytes allocated for s */
    /** what happens when memory runs out: 0 says so on stderr and ends the program with status 2 (a scanner has
     * nothing to save); 1 drops the text and sets failed */
    int keep_going,
    /** set when memory ran out with keep_going: every later put does nothing, so the owner asks once, at the end */
        failed;
} sb_t;

/**
 * @brief Appends bytes.
 *
 * @param[in,out] b the string
 * @param data the bytes
 * @param n how many
 * @pre b is not NULL; data holds n bytes.
 */
void sb_put(sb_t *b, const char *data, size_t n);
/**
 * @brief Appends formatted text.
 *
 * @param[in,out] b the string
 * @param fmt the printf format
 * @param ... its arguments
 * @pre b and fmt are not NULL.
 */
void sb_printf(sb_t *b, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
/**
 * @brief Appends a text as a JSON string, in its quotes.
 *
 * The bytes of a valid UTF-8 text go as they are, a quote, a backslash and a control character escaped; a byte that
 * does not start a UTF-8 sequence, or whose sequence is cut short, becomes U+FFFD, so the document stays a UTF-8 text.
 *
 * @param[in,out] b the string
 * @param s the text
 * @pre b and s are not NULL.
 */
void sb_str(sb_t *b, const char *s);

/**
 * @brief Parses a text that is one value.
 *
 * @param text the text
 * @return the value, to free with cJSON_Delete; NULL when the whole text is not one value
 */
cJSON *jparse(const char *text);
/**
 * @brief The member of an object.
 *
 * @param o the object
 * @param key the member's name, matched with case
 * @return the member, owned by o; NULL when o is not an object or has none
 */
cJSON *jget(const cJSON *o, const char *key);
/**
 * @brief The string member of an object.
 *
 * @param o the object
 * @param key the member's name
 * @return the string, owned by o; NULL when there is none or it is not a string
 */
const char *jstr(const cJSON *o, const char *key);
/**
 * @brief The number member of an object.
 *
 * @param o the object
 * @param key the member's name
 * @param[out] out the number, written only when there is one
 * @return 1 when the member is a number, else 0
 * @pre out is not NULL.
 */
int jnum(const cJSON *o, const char *key, double *out);
/**
 * @brief The boolean member of an object.
 *
 * @param o the object
 * @param key the member's name
 * @param def the answer when there is no boolean member
 * @return 1 or 0 for the boolean, or def
 */
int jbool(const cJSON *o, const char *key, int def);
/**
 * @brief The number of items of an array or object (for an object its key is jkey(o, k)).
 *
 * @param o the array or object
 * @return the count; 0 for any other value
 */
size_t jcount(const cJSON *o);
/**
 * @brief The k-th item of an array or object.
 *
 * @param o the array or object
 * @param k the index
 * @return the item, owned by o; NULL for any other value or an index out of range
 */
cJSON *jkid(const cJSON *o, size_t k);
/**
 * @brief The key of the k-th member of an object.
 *
 * @param o the object
 * @param k the index
 * @return the key, owned by o; NULL when there is no such item or it has no key
 */
const char *jkey(const cJSON *o, size_t k);

/** @brief One step of the path jraw follows. */
typedef struct
{
    const char *key; /**< the object member's name, as plain bytes with no escapes; NULL for an array item */
    size_t index;    /**< the array item's index, read when key is NULL */
} jstep_t;
/**
 * @brief The bytes of one value of a text jparse has accepted, as they are written there.
 *
 * Each step takes the object member `key` or the array item `index` of the value before it, from the text's own value.
 *
 * @param text the text
 * @param path the steps, from the text's own value
 * @param steps the number of steps
 * @param[out] len the length of the value's bytes, written only when the value is found
 * @return the start of the value in text; NULL when a step is not there
 * @pre text is a text jparse accepts; path holds steps steps; len is not NULL.
 */
const char *jraw(const char *text, const jstep_t *path, size_t steps, size_t *len);

#endif
