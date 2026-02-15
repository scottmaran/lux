# Platform Support
Layer: Contract

This document defines which environments Lasso currently supports and what a user
can rely on when running Lasso in those environments.

## Supported Environments
- Host OS: macOS with Docker Desktop installed and running.
- Linux host runtime support is currently best-effort and not guaranteed (as of
  February 2026).
- CPU architectures: x86_64 and arm64.
- Container runtime: Docker (via Docker Desktop).
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
- Architecture topology: `docs/architecture/deployments/lasso_vm_layout.md`
- Docker Desktop VM notes: `docs/architecture/deployments/docker_desktop_vm.md`
- Kernel auditing reference: `docs/architecture/sensors/kernel_auditing_info.md`
- Install steps: `docs/contracts/install.md`
