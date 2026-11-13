/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 *
 * The least privilege of every process the daemon starts that runs plugin code: a worker, the descriptor scan and the
 * probe runner's child (#61). */
#ifndef CONFINE_H
#define CONFINE_H

/* In a child after fork, before the exec of a program that runs plugin code (a worker, the descriptor scan, the probe's
 * child): no new privileges, no descriptor past 0, 1 and 2 but the nkeep of keep (the probe's step records and lock
 * report, its exec-failure pipe), and a seccomp filter that answers EPERM to the system calls no plugin needs (ptrace,
 * process_vm_readv/writev, mount, kexec, module loading, reboot, swap, bpf, userfaultfd and the like). -1 when no new
 * privileges cannot be set, and the caller does not exec: this is the one place a worker or a probe child is given it
 * (#68). A descriptor or seccomp step the kernel refuses is skipped; none of them touches scheduling, memory locking or
 * the audio path. */
int proc_confine(const int *keep, int nkeep);

#endif
