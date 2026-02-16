# `merge_filtering.yaml` (Merge Config)
Layer: Contract

This file configures the merge stage (`collector-merge-filtered`), which
combines filtered audit + summarized eBPF rows into one unified timeline file
(`timeline.filtered.v1`).

File:
- `collector/config/merge_filtering.yaml`

Schema:
- Output schema contract: `docs/contracts/schemas/timeline.filtered.v1.md`

## Runtime wiring (env overrides)
- `COLLECTOR_MERGE_CONFIG`: config file path
- `COLLECTOR_FILTER_OUTPUT`: filtered audit JSONL input path override (for `source: audit` inputs)
- `COLLECTOR_EBPF_SUMMARY_OUTPUT`: eBPF summary JSONL input path override (for `source: ebpf` inputs)
- `COLLECTOR_MERGE_FILTER_OUTPUT`: merged timeline JSONL output path

## Key fields (current)

`schema_version`
- Schema version string written into each merged row (default:
  `timeline.filtered.v1`).

`inputs`
- A list of input files, each with:
  - `path`: JSONL path
  - `source`: source label (`audit` or `ebpf`)

Runtime overrides:
- For `source: audit`, the merge can override the path with `COLLECTOR_FILTER_OUTPUT`.
- For `source: ebpf`, the merge can override the path with `COLLECTOR_EBPF_SUMMARY_OUTPUT`.

`output.jsonl`
- Output unified timeline JSONL path.
- Can be overridden by `COLLECTOR_MERGE_FILTER_OUTPUT`.

`sorting.strategy`
- Current supported value: `ts_source_pid`
  - Sort by timestamp, then source, then pid.

## Normalization rule: `details`
The merger normalizes each input row to:
- keep a standard envelope (`schema_version`, `session_id`, `job_id`, `ts`,
  `source`, `event_type`, pid/uid/comm/exe fields),
- move all non-envelope fields into `details`.

This keeps the UI and API consumption stable as upstream per-source schemas
evolve.
