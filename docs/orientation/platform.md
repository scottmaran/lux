# Platform

## Scope
- Supported hosts: macOS and Linux running Docker Desktop.
- Execution boundary is the Docker Desktop Linux VM; all audit happens inside that VM.
- Default container base distro: Ubuntu 22.04 LTS (agent, harness, collector).
- Container runtime: Docker; orchestration via Docker Compose.
- Supported topology is locked to VM + containers + host sink (see `docs/vm/lasso_vm_layout.md`).
- CPU architectures: x86_64 and arm64.
- Docker Desktop VM details: `docs/vm/docker_desktop_vm.md`.

## Kernel audit requirements (TODO)
- TODO: Specify kernel features and minimum versions for audit sources (auditd/eBPF/etc).
- TODO: Confirm required privileges/capabilities for the collector inside the VM.
