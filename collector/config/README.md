# Collector Config Index

This directory contains the configuration and rule files used by the collector
container.

Most users should not need to edit these. When making PRs, treat these files as
part of the collector's external contract: changes must be reflected in schema
docs and tests.

## Config files (by stage)

auditd runtime:
- `collector/config/auditd.conf`
  - Documented in: `collector/config/auditd.md`
  - Note: `collector/entrypoint.sh` rewrites `log_file = ...` at runtime based
    on `COLLECTOR_AUDIT_LOG` (or `COLLECTOR_AUDIT_OUTPUT`).

auditd rules:
- `collector/config/rules.d/harness.rules`
  - Documented in: `collector/config/auditd_rules.md`
  - Keys emitted by these rules (`key="..."`) drive downstream filtering.

audit filter:
- `collector/config/filtering.yaml`
  - Documented in: `collector/config/audit_filtering.md`
  - Consumed by: `collector-audit-filter` (`collector/scripts/filter_audit_logs.py`)
  - Output: `auditd.filtered.v1` (`filtered_audit.jsonl`)

eBPF filter:
- `collector/config/ebpf_filtering.yaml`
  - Documented in: `collector/config/ebpf_filtering.md`
  - Consumed by: `collector-ebpf-filter` (`collector/scripts/filter_ebpf_logs.py`)
  - Output: `ebpf.filtered.v1` (`filtered_ebpf.jsonl`)

eBPF summary:
- `collector/config/ebpf_summary.yaml`
  - Documented in: `collector/config/ebpf_summary.md`
  - Consumed by: `collector-ebpf-summary` (`collector/scripts/summarize_ebpf_logs.py`)
  - Output: `ebpf.summary.v1` (`filtered_ebpf_summary.jsonl`)

merge:
- `collector/config/merge_filtering.yaml`
  - Documented in: `collector/config/merge_filtering.md`
  - Consumed by: `collector-merge-filtered` (`collector/scripts/merge_filtered_logs.py`)
  - Output: `timeline.filtered.v1` (`filtered_timeline.jsonl`)

## Env overrides (runtime wiring)
The collector entrypoint supports env overrides for all key paths. Common ones:
- `COLLECTOR_AUDIT_LOG`: raw audit log path
- `COLLECTOR_EBPF_OUTPUT`: raw eBPF JSONL path
- `COLLECTOR_FILTER_OUTPUT`: filtered audit JSONL path
- `COLLECTOR_EBPF_FILTER_OUTPUT`: filtered eBPF JSONL path
- `COLLECTOR_EBPF_SUMMARY_OUTPUT`: eBPF summary JSONL path
- `COLLECTOR_MERGE_FILTER_OUTPUT`: merged timeline JSONL path

