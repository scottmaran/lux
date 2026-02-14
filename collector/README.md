# Collector

The collector runs inside the Docker Desktop Linux VM and observes OS-level
events from the agent + harness containers:
- auditd: exec + filesystem write/change + metadata change events (no reads)
- eBPF: network egress + IPC connection metadata (Unix sockets, plus DNS when available)

It writes raw logs to the sink and runs a pipeline to produce a unified,
UI-friendly timeline.

## Pipeline (run-scoped files)
In normal `lasso up` usage, outputs are run-scoped under:
`/logs/<run_id>/collector/...`.

Stages and files:
1) Raw auditd
   - `collector/raw/audit.log`
   - Contract: `collector/auditd_raw_data.md`
2) Raw eBPF
   - `collector/raw/ebpf.jsonl`
   - Contract: `collector/ebpf_raw_data.md`
3) Filter auditd (ownership + normalization)
   - `collector/filtered/filtered_audit.jsonl` (`auditd.filtered.v1`)
   - Contract: `collector/auditd_filtered_data.md`
4) Filter eBPF (ownership + optional cmd linking)
   - `collector/filtered/filtered_ebpf.jsonl` (`ebpf.filtered.v1`)
   - Contract: `collector/ebpf_filtered_data.md`
5) Summarize eBPF network into bursts
   - `collector/filtered/filtered_ebpf_summary.jsonl` (`ebpf.summary.v1`)
   - Contract: `collector/ebpf_summary_data.md`
6) Merge into unified timeline
   - `collector/filtered/filtered_timeline.jsonl` (`timeline.filtered.v1`)
   - Contract: `collector/timeline_filtered_data.md`

Attribution model:
- `collector/ownership_and_attribution.md`

## Stage Map (Code, Config, Schemas, Tests)

This is the "time to first PR" navigation hub: each stage links to the code,
config, schema contract, and the canonical unit + fixture coverage.

| Stage | Code | Config | Schema | Unit tests | Fixtures |
|---|---|---|---|---|---|
| audit filter | `collector/scripts/filter_audit_logs.py` | `collector/config/audit_filtering.yaml` | `collector/auditd_filtered_data.md` | `tests/unit/collector/test_audit_filter.py` | `tests/fixture/audit_filter/` |
| eBPF filter | `collector/scripts/filter_ebpf_logs.py` | `collector/config/ebpf_filtering.yaml` | `collector/ebpf_filtered_data.md` | `tests/unit/collector/test_ebpf_filter.py` | `tests/fixture/ebpf_filter/` |
| eBPF summary | `collector/scripts/summarize_ebpf_logs.py` | `collector/config/ebpf_summary.yaml` | `collector/ebpf_summary_data.md` | `tests/unit/collector/test_ebpf_summary.py` | `tests/fixture/summary/` |
| merge | `collector/scripts/merge_filtered_logs.py` | `collector/config/merge_filtering.yaml` | `collector/timeline_filtered_data.md` | `tests/unit/collector/test_merge_filtered.py` | `tests/fixture/merge/` |

## Implementation notes
- `collector/Dockerfile` builds the eBPF program + loader (Rust + Aya) and ships
  the artifacts into the runtime image.
- `collector/entrypoint.sh` boots auditd, loads rules, starts both filters in
  follow mode, runs the eBPF loader, and periodically runs summary + merge.

## Configuration
Config and env override reference lives under `collector/config/`:
- Index: `collector/config/README.md`
- auditd runtime: `collector/config/auditd.conf` (documented in `collector/config/auditd.md`)
- audit rules: `collector/config/rules.d/harness.rules` (documented in `collector/config/auditd_rules.md`)
- audit filter: `collector/config/audit_filtering.yaml` (documented in `collector/config/audit_filtering.md`)
- eBPF filter: `collector/config/ebpf_filtering.yaml` (documented in `collector/config/ebpf_filtering.md`)
- eBPF summary: `collector/config/ebpf_summary.yaml` (documented in `collector/config/ebpf_summary.md`)
- merge: `collector/config/merge_filtering.yaml` (documented in `collector/config/merge_filtering.md`)

## Testing
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
