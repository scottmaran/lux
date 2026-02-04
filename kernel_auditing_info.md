# Kernel Auditing Reference

## Audit sources (high level)
- Kernel audit subsystem (auditd): syscall-based audit events with strong PID/UID attribution.
- eBPF tracing: in-kernel programs attached to tracepoints/kprobes/LSM/cgroup hooks.
- HTTP(S) proxy (optional/future): method/URL/status for HTTP traffic; no payloads.
- Netfilter/conntrack logs: network metadata without reliable PID attribution (optional).

## What eBPF is and how it works
- eBPF runs small, verified programs inside the Linux kernel when specific events occur.
- Programs attach to tracepoints, kprobes/uprobes, cgroup hooks, and socket events.
- Events are sent to user space via perf or ring buffers; maps provide shared state.
- Strengths: flexible event capture, strong PID attribution, good network/IPC visibility.
- Trade-offs: more complex tooling; depends on kernel config and requires privileges.

## What auditd is and how it works
- The kernel audit subsystem emits structured events for configured syscalls.
- auditd (or another netlink client) receives and formats those events.
- Strengths: reliable exec and file/metadata coverage; mature and stable.
- Trade-offs: limited network/IPC detail; can be verbose; one audit daemon per system.

## Hybrid approach used by the harness
- auditd for exec + filesystem writes/renames/unlinks + metadata changes (chmod/chown/xattr/utime).
- eBPF for network egress + local IPC connection metadata (Unix sockets, D-Bus) with PID attribution.
- Optional HTTP proxy logs method/URL/status; HTTPS without MITM logs host/port only.
- Correlate events by PID/PPID + session_id + timestamp; merge into a timeline.

## Docker Desktop Linux VM considerations
- Docker Desktop runs a LinuxKit-based Linux VM; the audit boundary is the VM kernel.
- LinuxKit kernel configs include common audit and tracing features such as:
  `CONFIG_AUDIT`, `CONFIG_AUDITSYSCALL`, `CONFIG_BPF`, `CONFIG_BPF_SYSCALL`,
  `CONFIG_BPF_JIT`, `CONFIG_CGROUP_BPF`, `CONFIG_BPF_EVENTS`, `CONFIG_KPROBES`,
  `CONFIG_UPROBES`, `CONFIG_TRACEPOINTS`, `CONFIG_PERF_EVENTS`, `CONFIG_FTRACE`,
  `CONFIG_FTRACE_SYSCALLS`.
- Kernel config can change across Docker Desktop releases; verify per version.
- Enhanced Container Isolation (ECI) can restrict kernel access; the collector
  must be permitted to access audit/eBPF interfaces.
