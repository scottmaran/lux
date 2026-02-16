# `ebpf_summary.yaml` (eBPF Summary Config)
Layer: Contract

This file configures the eBPF summary stage (`collector-ebpf-summary`), which
turns filtered eBPF events into burst-level `net_summary` rows.

File:
- `collector/config/ebpf_summary.yaml`

Schema:
- Output schema contract: `docs/contracts/schemas/ebpf.summary.v1.md`

## Runtime wiring (env overrides)
- `COLLECTOR_EBPF_SUMMARY_CONFIG`: config file path
- `COLLECTOR_EBPF_FILTER_OUTPUT`: filtered eBPF JSONL input path
- `COLLECTOR_EBPF_SUMMARY_OUTPUT`: summary JSONL output path

## Key fields (current)

`schema_version`
- Output schema version written into each row (default `ebpf.summary.v1`).

`input.jsonl`
- Input filtered eBPF file (default `<log_root>/filtered_ebpf.jsonl`).
- Often overridden by `COLLECTOR_EBPF_FILTER_OUTPUT`.

`output.jsonl`
- Output summary file (default `<log_root>/filtered_ebpf_summary.jsonl`).
- Often overridden by `COLLECTOR_EBPF_SUMMARY_OUTPUT`.

`burst_gap_sec`
- Split bursts when the idle gap between sends exceeds this many seconds.

`dns_lookback_sec`
- Include DNS answers observed within this many seconds *before* burst start
  when building `dns_names`.

`min_send_count` / `min_bytes_sent_total`
- Burst suppression thresholds.
- A burst is dropped only if BOTH thresholds are met (`<=`).
