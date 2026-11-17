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
 * @brief The daemon's feedback port, and the workers' feedback read on a thread of its own and written to it.
 *
 * PHD_RELAY in \<plugin-hostd/protocol.h\>. The daemon's own events and the workers' lines share one writer under one
 * lock, so no two lines are ever cut into each other. Unless a function says otherwise it takes that lock and may be
 * called from any thread.
 */

#ifndef RELAY_H
#define RELAY_H

#include <stddef.h>

/**
 * @brief Sets the function that writes what every feedback line starts with; none until set.
 *
 * The function writes the prefix NUL-terminated in buf (the session's "#\<n\> " under seq) and is called under the
 * relay's lock, once for each line sent, also for a line that cannot be sent.
 *
 * @param prefix writes the prefix into buf, of room size, and returns its length; NULL for none
 * @note Not thread-safe: the pointer is set without the lock; call before any worker's socket is added.
 */
void relay_set_prefix(size_t (*prefix)(char *buf, size_t size));

/**
 * @brief Listens on `port`, 0 for none, and starts the thread that reads the workers.
 *
 * @param port the feedback port, or 0 for none
 * @param address the IPv4 address to listen on; read when port is not 0
 * @return 0, or -1 when the pipe, the socket, the address, the bind or the thread fails
 * @pre address is not NULL when port is not 0. Called once.
 * @note Not thread-safe: call on the daemon's main thread, before any other relay function but relay_set_prefix.
 */
int relay_start(int port, const char *address);
/**
 * @brief Stops the thread and closes every worker's feedback socket, the controller's and the listening socket.
 *
 * Every gesture a worker held is ended at the controller before its connection is closed.
 *
 * @note Not thread-safe: call on the daemon's main thread, once no other thread calls the relay.
 */
void relay_finish(void);

/**
 * @brief Waits for a controller to open the feedback port, as mod-host does before its first command.
 *
 * Returns at once when there is no feedback port or a controller is on it already; else it waits until one connects
 * or *running goes to 0.
 *
 * @param running the daemon's running flag
 * @pre running is not NULL.
 * @note Call on the daemon's main thread: the listening socket is read without the lock.
 */
void relay_await_controller(volatile int *running);

/** @brief Closes the feedback connection of a controller that went away; the next controller opens its own. */
void relay_controller_gone(void);

/**
 * @brief Sends one line of the daemon's own, an event, to the controller.
 *
 * The line goes whole, with its NUL, or not at all: nothing is sent when no controller holds the feedback port or a
 * send to it has failed.
 *
 * @param line the line
 * @pre line is not NULL.
 */
void relay_event(const char *line);

/**
 * @brief Takes a worker's feedback socket: it is set non-blocking and read from now on.
 *
 * @param fd the socket
 * @return 0; -1 for an fd below 0, or when there is no memory to follow it: the socket is closed then, so the worker's
 *         writes fail instead of blocking, and the caller no longer holds it
 */
int relay_add(int fd);

/**
 * @brief Closes a worker's feedback socket: what the worker wrote before it is read and sent first.
 *
 * Every gesture the worker held is ended at the controller. An fd below 0 does nothing; an fd the relay does not
 * follow is closed all the same.
 *
 * @param fd the socket
 */
void relay_remove(int fd);

/**
 * @brief The last xruns count (PHD_EVENT_XRUNS) the worker of this feedback socket wrote, read up to now.
 *
 * The count is the worker's own, cumulative since it started.
 *
 * @param fd the worker's feedback socket
 * @param[out] count the count, written on 1 only
 * @return 1, or 0 when it has written none since the socket was added (a worker that counted no xrun writes none) or
 *         the relay does not follow the socket
 * @pre count is not NULL.
 */
int relay_xruns(int fd, unsigned long long *count);

/**
 * @brief The instances the worker of this feedback socket said abi_clobber of (PHD_EVENT_ABI_CLOBBER) since the last
 *        call.
 *
 * Only what the relay's thread has read so far is given. Each is given once, and what did not fit waits for the next
 * call. An instance removed meanwhile (relay_instance_gone) is not given.
 *
 * @param fd the worker's feedback socket
 * @param[out] ids up to max instance ids
 * @param max the room in ids
 * @return the number written to ids
 * @pre ids holds room for max ids.
 */
int relay_abi_clobbers(int fd, int *ids, int max);

/**
 * @brief The instances whose plugin moved a value of its own since the last call, as relay_abi_clobbers gives them.
 *
 * A plugin moved a value when the worker of this feedback socket wrote a PHD_EVENT_PARAM_SET line for the instance.
 *
 * @param fd the worker's feedback socket
 * @param[out] ids up to max instance ids, each once; what did not fit waits for the next call
 * @param max the room in ids
 * @return the number written to ids
 * @pre ids holds room for max ids.
 */
int relay_param_moves(int fd, int *ids, int max);

/**
 * @brief Ends at the controller every gesture a removed instance held, once, whichever worker the instance was on.
 *
 * What each worker wrote so far is read and sent first, and the abi_clobber and value-move reports of the instance
 * that were not taken yet are dropped.
 *
 * @param id the instance
 */
void relay_instance_gone(int id);

#endif
