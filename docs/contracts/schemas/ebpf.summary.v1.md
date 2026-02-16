# eBPF Summary Data Schema (`ebpf.summary.v1`)
Layer: Contract

This document defines the JSONL emitted by the eBPF summary stage
(`collector-ebpf-summary`), which collapses noisy raw network activity into
UI-friendly `net_summary` rows.

Where it shows up:
- In a run-scoped deployment, this file is typically
  `<log_root>/<run_id>/collector/filtered/filtered_ebpf_summary.jsonl`.
- The exact path is controlled by `COLLECTOR_EBPF_SUMMARY_OUTPUT`.

Upstream and downstream:
- Input: `docs/contracts/schemas/ebpf.filtered.v1.md` (`ebpf.filtered.v1`, `filtered_ebpf.jsonl`)
- Merge into timeline: `docs/contracts/schemas/timeline.filtered.v1.md` (`timeline.filtered.v1`)

## Row format
- The file is JSONL (one JSON object per line).
- Rows are ordered by timestamp (`ts`) when written, but treat it as an
  append/refresh artifact (the collector rewrites this file periodically).

## What this stage emits
This file can contain two row shapes:

1) `event_type="net_summary"` rows (newly synthesized).
2) `event_type="unix_connect"` rows passed through from the filtered eBPF
   stream, with only `schema_version` rewritten to `ebpf.summary.v1`.

The merge stage consumes this file by default so the unified timeline contains:
- `net_summary` for network egress
- `unix_connect` for IPC metadata

## Ownership and attribution
- This stage drops still-unattributed rows (`session_id="unknown"` with no
  `job_id`) instead of emitting ownerless timeline rows.
- Rows are either session-owned (`session_id != "unknown"`) or job-owned
  (`session_id="unknown"` with `job_id`).

## Common fields
Required unless noted.

- `schema_version` (string): fixed `ebpf.summary.v1`
- `session_id` (string)
- `job_id` (string, optional)
- `ts` (string): RFC3339 timestamp
  - for `net_summary`, `ts` is the burst start time (UTC, millisecond precision)
  - for passthrough `unix_connect`, `ts` is preserved from the filtered input
- `source` (string): fixed `ebpf`
- `event_type` (string): `net_summary` or `unix_connect`

## `net_summary` fields
These rows represent **send bursts** to one destination (split by idle gaps).

- `pid` (int)
- `ppid` (int|null)
- `uid` (int|null)
- `gid` (int|null)
- `comm` (string)
- `dst_ip` (string)
- `dst_port` (int)
- `protocol` (string): best-effort (`tcp`, `udp`, or `unknown`)
- `dns_names` (array[string]): DNS names observed within the burst window and a
  configured lookback window
- `connect_count` (int): number of `net_connect` events within the burst window
- `send_count` (int): number of send events in the burst
- `bytes_sent_total` (int): sum of sent bytes in the burst
- `ts_first` (string): same as burst start time
- `ts_last` (string): burst end time

Notes:
- Port 53 traffic is excluded from `net_summary` (DNS is tracked separately for
  name correlation).
- DNS correlation is driven by `dns_response` rows: the summarizer maps
  `answer_ip -> query_name` and then attaches names to bursts that send to those
  IPs.

## `unix_connect` passthrough fields
`unix_connect` rows are passed through from `ebpf.filtered.v1` with only
`schema_version` changed. See `docs/contracts/schemas/ebpf.filtered.v1.md` for the full
field list.

## Example: `net_summary`
```json
{
  "schema_version": "ebpf.summary.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:16:30.535Z",
  "source": "ebpf",
  "event_type": "net_summary",
  "pid": 956,
  "ppid": 943,
  "uid": 1001,
  "gid": 1001,
  "comm": "tokio-runtime-w",
  "dst_ip": "104.18.32.47",
  "dst_port": 443,
  "protocol": "tcp",
  "dns_names": ["chatgpt.com"],
  "connect_count": 1,
  "send_count": 5,
  "bytes_sent_total": 1240,
  "ts_first": "2026-01-22T00:16:30.535Z",
  "ts_last": "2026-01-22T00:16:30.847Z"
}
```
