/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com> */
/* Put before every other include directory by make test-fuzz-no-openssl: a fuzz harness source that reaches OpenSSL
 * fails. */
#error "a fuzz harness source must not need OpenSSL"
