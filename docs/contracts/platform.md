# Platform Support
Layer: Contract

This document defines which environments Lux currently supports and what a user
can rely on when running Lux in those environments.

## Supported Environments
- Host OS: macOS or Linux.
- Docker runtime installed and running on the host.
- CPU architectures: x86_64 and arm64.
- Container runtime: Docker.
- Observation boundary (current): the Docker Desktop Linux VM.

## What This Means
- OS-level auditing happens inside the Docker Desktop Linux VM boundary.
- Evidence is written to a host sink outside the VM, and the agent must not have
  write access to that sink.

## Known Caveats
- Claude host-state caveat (macOS): mounted `~/.claude*` files can be insufficient
  when host auth depends on macOS Keychain; API-key mode is the deterministic
  fallback for container auth.

## Related
- Architecture topology: `docs/architecture/deployments/lux_vm_layout.md`
- Docker Desktop VM notes: `docs/architecture/deployments/docker_desktop_vm.md`
- Kernel auditing reference: `docs/architecture/sensors/kernel_auditing_info.md`
- Install steps: `docs/contracts/install.md`
