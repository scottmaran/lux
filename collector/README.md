# Overview
The collector container to audit the VM OS that the agent and harness containers live in.

# Implementation

## dockerfile
Uses Ubuntu 22.04 LTS to stay aligned with the platform default and keep auditd behavior predictable across environments. Includes a Rust build stage that compiles the custom eBPF programs and loader (Aya), then copies the artifacts into the final image. Installs `auditd` plus `audispd-plugins` for future forwarding options, and `util-linux` for mount utilities.

## entrypoint.sh
Bootstraps auditd, the audit log filter, and the custom eBPF loader without forcing the container to exit on non-fatal rule errors. It ensures the log files exist and are writable by the audit group, starts auditd in daemon mode, then launches the filter (`collector-audit-filter`) and the eBPF loader with paths controlled by `COLLECTOR_AUDIT_LOG`, `COLLECTOR_FILTER_CONFIG`, `COLLECTOR_FILTER_OUTPUT`, `COLLECTOR_EBPF_OUTPUT`, and `COLLECTOR_EBPF_BPF`.

In normal `lasso up` usage, these env vars are run-scoped, e.g.
`/logs/<run_id>/collector/raw/*` and `/logs/<run_id>/collector/filtered/*`.

## auditd.conf
Configured to keep audit output local and file‑backed: `local_events = yes`, RAW log
format, and an explicit `log_file` under `/logs`. Rotation is enabled with small log
chunks for local testing, and disk‑pressure actions are conservative (SUSPEND) to avoid silent loss. The log group is `adm` (Ubuntu standard).

## harness.rules
Keeps scope narrow and attribution‑focused. It logs exec events for process lineage and audits only writes/renames/unlinks plus metadata changes inside `/work` (no reads). The rules use a mix of path watches and syscall filters for coverage, and avoid syscalls that don’t exist on aarch64 kernels. This is a starter set intended to be refined for noise reduction and tighter scoping later.

Schema reference: `collector/eBPF_data.md`.

# Testing
Canonical testing is Python/pytest via `uv`.

Primary entrypoints:
- `uv run python scripts/all_tests.py --lane fast`
- `uv run python scripts/all_tests.py --lane pr`
- `uv run python scripts/all_tests.py --lane full`

Collector-specific smoke coverage for raw audit + eBPF signals:
- `uv run pytest tests/integration/test_collector_raw_smoke.py -q`

For the complete testing contract, required gates, and layer boundaries, see:
- `tests/README.md`
- `tests/test_principles.md`
