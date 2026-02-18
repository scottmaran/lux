# Platform Notes
Layer: Implementation

This document captures current platform constraints, implementation notes, and
TODOs. It is not the external support contract (see `docs/contracts/platform.md`).

## Current Deployment Model (Today)
- Default container base distro: Ubuntu 22.04 LTS (agent, harness, collector).
- Orchestration: Docker Compose (`compose.yml`).
- Supported topology today is VM + containers + host sink.

See:
- `docs/architecture/deployments/lux_vm_layout.md`
- `docs/architecture/deployments/docker_desktop_vm.md`

## Kernel Audit Requirements (TODO)
- Specify kernel features and minimum versions required for audit sources
  (auditd/eBPF/etc).
- Confirm required privileges/capabilities for the collector inside the VM.
