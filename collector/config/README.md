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
- `collector/config/audit_filtering.yaml`
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

## Run-scoped wiring (important)
Several shipped config files include "flat" defaults like `/logs/filtered_*.jsonl`
and `/logs/sessions`. In real runs, `compose.yml` sets env vars so the
collector reads/writes run-scoped paths under `/logs/${LASSO_RUN_ID}/...`.

If you are debugging attribution issues, these env vars matter:
- `COLLECTOR_SESSIONS_DIR`: points to `.../harness/sessions` for the active run.
- `COLLECTOR_JOBS_DIR`: points to `.../harness/jobs` for the active run.
- `COLLECTOR_ROOT_COMM`: provider-specific root comm allowlist (comma-separated).

## Env overrides (runtime wiring)
The collector entrypoint supports env overrides for all key paths. Common ones:
- `COLLECTOR_AUDIT_LOG`: raw audit log path
- `COLLECTOR_EBPF_OUTPUT`: raw eBPF JSONL path
- `COLLECTOR_FILTER_OUTPUT`: filtered audit JSONL path
- `COLLECTOR_EBPF_FILTER_OUTPUT`: filtered eBPF JSONL path
- `COLLECTOR_EBPF_SUMMARY_OUTPUT`: eBPF summary JSONL path
- `COLLECTOR_MERGE_FILTER_OUTPUT`: merged timeline JSONL path
- `COLLECTOR_SESSIONS_DIR`: sessions metadata directory (run-scoped)
- `COLLECTOR_JOBS_DIR`: jobs metadata directory (run-scoped)
- `COLLECTOR_ROOT_COMM`: root comm override for both audit + eBPF filters

Config path overrides:
- `COLLECTOR_FILTER_CONFIG`: audit filter config path
- `COLLECTOR_EBPF_FILTER_CONFIG`: eBPF filter config path
- `COLLECTOR_EBPF_SUMMARY_CONFIG`: eBPF summary config path
- `COLLECTOR_MERGE_CONFIG`: merge config path
