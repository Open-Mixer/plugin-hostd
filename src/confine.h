/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com> */
/** @file confine.h
 * @brief The least privilege of every process the daemon starts that runs plugin code.
 *
 * Those processes are a worker, the descriptor scan and the probe runner's child.
 */

#ifndef CONFINE_H
#define CONFINE_H

/**
 * @brief Confines the calling process: for a child after fork, before the exec of a program that runs plugin code.
 *
 * Three steps: no new privileges; every descriptor past 0, 1 and 2 closed but the nkeep of keep (the probe's step
 * records and lock report, its exec-failure pipe); and a seccomp filter that answers EPERM to the system calls no
 * plugin needs (ptrace, process_vm_readv/writev, mount, kexec, module loading, reboot, swap, bpf, userfaultfd and the
 * like) and to every system call of another architecture than the build's. A descriptor or seccomp step the kernel
 * refuses is skipped; none of them touches scheduling, memory locking or the audio path. This is the one place a
 * worker or a probe child is given no new privileges.
 *
 * @param keep the descriptors to leave open besides 0, 1 and 2; may be NULL when nkeep is 0
 * @param nkeep the number of descriptors in keep
 * @return 0, or -1 when no new privileges cannot be set: nothing else was done, and the caller does not exec
 */
int proc_confine(const int *keep, int nkeep);

#endif
