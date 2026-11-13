/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 *
 * The least privilege of every process the daemon starts that runs plugin code: a worker, the descriptor scan and the
 * probe runner's child (#61). */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <errno.h>
#include <stddef.h>
#include <unistd.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/syscall.h>

#include "confine.h"

/* ---------------------------------------------------------------- least privilege of a plugin process */

#if defined(__x86_64__)
#define CONFINE_ARCH AUDIT_ARCH_X86_64
#elif defined(__aarch64__)
#define CONFINE_ARCH AUDIT_ARCH_AARCH64
#elif defined(__arm__)
#define CONFINE_ARCH AUDIT_ARCH_ARM
#elif defined(__i386__)
#define CONFINE_ARCH AUDIT_ARCH_I386
#endif

/* what no plugin and no JACK client needs: another process's memory, the mounts, the kernel and its modules, the
 * machine's power and swap, raw handles past the file permissions, BPF and userfaultfd. Each answers EPERM: a plugin
 * that tries one gets an error, the audio of the process goes on */
static const int g_denied[] = {
#ifdef __NR_ptrace
    __NR_ptrace,
#endif
#ifdef __NR_process_vm_readv
    __NR_process_vm_readv,
#endif
#ifdef __NR_process_vm_writev
    __NR_process_vm_writev,
#endif
#ifdef __NR_mount
    __NR_mount,
#endif
#ifdef __NR_umount2
    __NR_umount2,
#endif
#ifdef __NR_pivot_root
    __NR_pivot_root,
#endif
#ifdef __NR_kexec_load
    __NR_kexec_load,
#endif
#ifdef __NR_kexec_file_load
    __NR_kexec_file_load,
#endif
#ifdef __NR_init_module
    __NR_init_module,
#endif
#ifdef __NR_finit_module
    __NR_finit_module,
#endif
#ifdef __NR_delete_module
    __NR_delete_module,
#endif
#ifdef __NR_reboot
    __NR_reboot,
#endif
#ifdef __NR_swapon
    __NR_swapon,
#endif
#ifdef __NR_swapoff
    __NR_swapoff,
#endif
#ifdef __NR_acct
    __NR_acct,
#endif
#ifdef __NR_open_by_handle_at
    __NR_open_by_handle_at,
#endif
#ifdef __NR_bpf
    __NR_bpf,
#endif
#ifdef __NR_userfaultfd
    __NR_userfaultfd,
#endif
#ifdef __NR_iopl
    __NR_iopl,
#endif
#ifdef __NR_ioperm
    __NR_ioperm,
#endif
};

#define DENIED_N ((int)(sizeof(g_denied) / sizeof(g_denied[0])))

/* the filter: a system call of another architecture than the build's (the i386 entry of an x86_64 process, x32) is
 * refused too, or the list could be walked around through it */
static void confine_syscalls(void)
{
#ifdef CONFINE_ARCH
    struct sock_filter f[DENIED_N + 8];
    struct sock_fprog prog;
    int n = 0, k;

    f[n++] = (struct sock_filter)BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch));
    f[n++] = (struct sock_filter)BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, CONFINE_ARCH, 1, 0);
    f[n++] = (struct sock_filter)BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    f[n++] = (struct sock_filter)BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr));
#if defined(__x86_64__)
    f[n++] = (struct sock_filter)BPF_JUMP(BPF_JMP | BPF_JGE | BPF_K, 0x40000000, DENIED_N + 1, 0);
#endif
    for (k = 0; k < DENIED_N; k++)
        f[n++] = (struct sock_filter)BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (unsigned)g_denied[k], DENIED_N - k, 0);
    f[n++] = (struct sock_filter)BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW);
    f[n++] = (struct sock_filter)BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    prog.len = (unsigned short)n;
    prog.filter = f;
    /* a kernel without seccomp leaves the process as it was: the filter is a layer, never a reason not to run */
    (void)prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog);
#endif
}

/* whether fd is one of the n of keep */
static int kept(int fd, const int *keep, int n)
{
    int k;

    for (k = 0; k < n; k++)
        if (keep[k] == fd)
            return 1;
    return 0;
}

/* every descriptor past stdin, stdout and stderr but the n of keep: the command socket, a controller's, another
 * worker's, the pin store, the runner's pipes */
static void close_inherited(const int *keep, int n)
{
    struct rlimit rl;
    long fd, max = 65536;

#ifdef __NR_close_range
    if (n == 0 && syscall(__NR_close_range, 3U, ~0U, 0U) == 0)
        return;
#endif
    if (getrlimit(RLIMIT_NOFILE, &rl) == 0 && rl.rlim_cur != RLIM_INFINITY && (long)rl.rlim_cur < max)
        max = (long)rl.rlim_cur;
    for (fd = 3; fd < max; fd++)
        if (!kept((int)fd, keep, n))
            close((int)fd);
}

int proc_confine(const int *keep, int nkeep)
{
    /* nothing the process execs can gain a privilege (setuid, file capabilities); real-time scheduling comes from
     * RLIMIT_RTPRIO or rtkit and is not one of them. The one place a worker or a probe child is given it (#68): a
     * process that cannot have it is not run */
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0)
        return -1;
    close_inherited(keep, nkeep);
    confine_syscalls();
    return 0;
}
