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

/** @file relay.h
 * @brief The declarations of relay.h.
 */

#ifndef RELAY_H
#define RELAY_H

#include <stddef.h>

/* The daemon's feedback port, and the workers' feedback read on a thread of its own and written to it (PHD_RELAY in
 * <plugin-hostd/protocol.h>). The daemon's own events and the workers' lines share one writer, so no two lines
 * are ever cut into each other. */

/**
 * @brief Sets what every feedback line starts with, written NUL-terminated in buf (the session's "#\<n> " under seq); none
 * until set.
 * @param prefix writes the prefix into buf, of room size, and returns its length
 */
void relay_set_prefix(size_t (*prefix)(char *buf, size_t size));

/**
 * @brief Listens on `port`, 0 for none, and starts the thread that reads the workers.
 * @param port the feedback port, or 0 for none
 * @param address the IPv4 address to listen on; read when port is not 0
 * @return 0, or -1 when the pipe, the socket, the address, the bind or the thread fails
 */
int relay_start(int port, const char *address);
/**
 * @brief Stops the thread and closes every worker's feedback socket, the controller's and the listening socket.
 */
void relay_finish(void);

/**
 * @brief Before the first command of a controller: waits for it to open the feedback port, as mod-host does, until
 * *running goes to 0.
 *
 * Returns at once when there is no feedback port or a controller is on it already.
 * @param running the daemon's running flag
 */
void relay_await_controller(volatile int *running);

/**
 * @brief The controller went away: its feedback connection is closed, and the next controller opens its own.
 */
void relay_controller_gone(void);

/**
 * @brief One line of the daemon's own, an event, to the controller.
 * @param line the line
 */
void relay_event(const char *line);

/**
 * @brief Takes a worker's feedback socket: read from now on.
 * @param fd the socket
 * @return 0, or -1 when there is no memory to follow it: the socket is closed then, so the worker's writes fail instead
 *         of blocking, and the caller no longer holds it
 */
int relay_add(int fd);

/**
 * @brief Closes a worker's feedback socket: what the worker wrote before it is read and sent first.
 * @param fd the socket
 */
void relay_remove(int fd);

/**
 * @brief The last xruns count (PHD_EVENT_XRUNS) the worker of this feedback socket wrote, read up to now.
 *
 * The count is the worker's own, cumulative since it started.
 * @param fd the worker's feedback socket
 * @param[out] count the count
 * @return 1 and *count, or 0 when it has written none since the socket was added (a worker that counted no xrun writes
 *         none)
 */
int relay_xruns(int fd, unsigned long long *count);

/**
 * @brief The instances the worker of this feedback socket said abi_clobber of (PHD_EVENT_ABI_CLOBBER) since the last
 * call, read up to now.
 *
 * Each is given once, and what did not fit waits for the next call. An instance removed meanwhile (relay_instance_gone)
 * is not given.
 * @param fd the worker's feedback socket
 * @param[out] ids up to max instance ids
 * @param max the room in ids
 * @return the number written to ids
 */
int relay_abi_clobbers(int fd, int *ids, int max);

/**
 * @brief The instances whose plugin moved a value of its own (a PHD_EVENT_PARAM_SET line the worker of this feedback
 * socket wrote) since the last call, as relay_abi_clobbers gives them.
 * @param fd the worker's feedback socket
 * @param[out] ids up to max instance ids, each once; what did not fit waits for the next call
 * @param max the room in ids
 * @return the number written to ids
 */
int relay_param_moves(int fd, int *ids, int max);

/**
 * @brief An instance removed: every gesture it held is ended at the controller, once, whichever worker the instance was on.
 * @param id the instance
 */
void relay_instance_gone(int id);

#endif
