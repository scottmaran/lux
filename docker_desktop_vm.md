# Docker Desktop Linux VM

## Overview
- Docker Desktop runs Linux containers inside a Linux VM on macOS and on Linux.
- The VM boundary is the audit boundary; container processes run on the VM kernel.
- Containers and images live in a VM disk image; host file sharing is via VM file sharing (VirtioFS on Docker Desktop for Linux).
- On macOS, Docker Desktop uses a hypervisor backend (HyperKit historically; Apple Virtualization is now the default).

## Kernel and audit feature baseline
Docker Desktop uses a LinuxKit-based kernel. LinuxKit kernel configs for both x86_64 and arm64
include the following capabilities that matter for auditing:

- Audit subsystem: `CONFIG_AUDIT`, `CONFIG_AUDITSYSCALL`.
- eBPF core: `CONFIG_BPF`, `CONFIG_BPF_SYSCALL`, `CONFIG_BPF_JIT`,
  `CONFIG_CGROUP_BPF`, `CONFIG_BPF_EVENTS`.
- Tracing primitives: `CONFIG_TRACEPOINTS`, `CONFIG_PERF_EVENTS`,
  `CONFIG_KPROBES`, `CONFIG_UPROBES`, `CONFIG_FTRACE`, `CONFIG_FTRACE_SYSCALLS`.

Docker Desktop release notes also track kernel config changes (for example re-enabling
`CONFIG_AUDIT` and enabling `CONFIG_SECURITY`), which confirms that kernel config can
change between versions.

## Why auditing works in the Docker Desktop VM
- All agent processes and container workloads execute inside the VM, so kernel-level
  audit hooks observe them regardless of container boundaries.
- A privileged collector running in the VM can access audit and/or eBPF interfaces
  to capture exec, file-change, network, and IPC metadata.
- Logs can be persisted to the host sink via the VM's shared filesystem.

## Constraints and validation
- The VM kernel config is not user-tunable. If a required kernel feature is missing,
  use a self-managed VM where you control the kernel.
- Enhanced Container Isolation (ECI) can restrict access to kernel interfaces;
  ensure it is disabled or configured to allow the collector.
- Windows WSL2/Hyper-V backends are out of scope for this project.
