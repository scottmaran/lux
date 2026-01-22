# Overview
The collector container to audit the VM OS that the agent and harness containers live in.

# Implementation

## dockerfile
Uses Ubuntu 22.04 LTS to stay aligned with the platform default and keep auditd behavior
predictable across environments. Includes a Rust build stage that compiles the custom
eBPF programs and loader (Aya), then copies the artifacts into the final image. Installs
`auditd` plus `audispd-plugins` for future forwarding options, and `util-linux` for mount
utilities.

## entrypoint.sh
Bootstraps auditd and the custom eBPF loader without forcing the container to exit on
non-fatal rule errors. It ensures the log files exist and are writable by the audit
group, starts auditd in daemon mode, then launches the eBPF loader with paths controlled
by `COLLECTOR_AUDIT_LOG`, `COLLECTOR_EBPF_OUTPUT`, and `COLLECTOR_EBPF_BPF`.

The audit filter is specified in `collector/auditd_data.md` and
`collector/config/filtering_rules.md`; implementation is pending.

## auditd.conf
Configured to keep audit output local and file‑backed: `local_events = yes`, RAW log
format, and an explicit `log_file` under `/logs`. Rotation is enabled with small log
chunks for local testing, and disk‑pressure actions are conservative (SUSPEND) to avoid
silent loss. The log group is `adm` (Ubuntu standard).

## harness.rules
Keeps scope narrow and attribution‑focused. It logs exec events for process lineage and
audits only writes/renames/unlinks plus metadata changes inside `/work` (no reads). The
rules use a mix of path watches and syscall filters for coverage, and avoid syscalls that
don’t exist on aarch64 kernels. This is a starter set intended to be refined for noise
reduction and tighter scoping later.

Schema reference: `collector/eBPF_data.md`.

# Testing
Run the full test sequence with a single script:

collector/scripts/run_test.sh

The script builds the collector image, starts it with the required mounts, generates
filesystem + network/IPC activity, stops the collector, and prints log summaries. You
can override these environment variables if needed:

- `ROOT_DIR` (default: repo root)
- `WORKSPACE` (default: `ROOT_DIR/workspace`)
- `LOGS` (default: `ROOT_DIR/logs`)
- `IMAGE` (default: `harness-collector:dev`)
- `COLLECTOR_NAME` (default: `harness-collector`)

See `TESTING.md` for filter test cases and expected outputs.
