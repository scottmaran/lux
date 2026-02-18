# Kernel Auditing Reference
Layer: Implementation

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

## `auditctl` quick reference (common flags)
These are the most common `auditctl` flags you will see in rule sets and docs:

- `-w <path>`: add a watch to a file/dir path.
- `-p <perm>`: permissions mask for watches (for example `wa` for write+attribute).
- `-k <key>`: attach a string key to matching events (used downstream for filtering).
- `-F <field>=<value>`: add a field filter (only match events where a field has a value).
- `-S <syscall>[,<syscall>...]`: syscall filter for a rule (for example `-S execve,execveat`).
- `-a <list>,<action>`: append a rule to a list/action pair (for example `-a always,exit`).
- `-l`: list all currently loaded rules.
- `-D`: delete all rules (clear ruleset).
- `-t`: trim subtrees that appear after a mount command (advanced; rarely used in this repo).

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

## Lux schema references
- auditd raw (`audit.log`): `docs/contracts/schemas/auditd.raw.md`
- auditd filtered (`filtered_audit.jsonl`): `docs/contracts/schemas/auditd.filtered.v1.md`
- eBPF raw (`ebpf.jsonl`): `docs/contracts/schemas/ebpf.raw.md`
- eBPF filtered (`filtered_ebpf.jsonl`): `docs/contracts/schemas/ebpf.filtered.v1.md`
- eBPF summary (`filtered_ebpf_summary.jsonl`): `docs/contracts/schemas/ebpf.summary.v1.md`
- unified timeline (`filtered_timeline.jsonl`): `docs/contracts/schemas/timeline.filtered.v1.md`
- attribution model: `docs/contracts/attribution.md`
