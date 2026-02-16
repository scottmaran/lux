# Filtered Timeline Data Schema (`timeline.filtered.v1`)
Layer: Contract

This document defines the unified, filtered timeline emitted by the merger.
The UI should consume this file rather than raw audit/eBPF logs.

Upstream contracts:
- Audit filter output: `docs/contracts/schemas/auditd.filtered.v1.md` (`auditd.filtered.v1`)
- eBPF summary output: `docs/contracts/schemas/ebpf.summary.v1.md` (`ebpf.summary.v1`)

Where it shows up:
- In a run-scoped deployment, this file is typically
  `<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`.
- The exact path is controlled by `COLLECTOR_MERGE_FILTER_OUTPUT`.

File semantics (important):
- The merger rewrites the output file (it is not append-only).
- In live collector runs, the entrypoint refreshes this file periodically
  (default interval is 2 seconds). Consumers should treat it as a snapshot file
  and re-read/poll rather than assuming tail-only behavior.

## Schema version
- `schema_version`: fixed `timeline.filtered.v1`

## Common fields (all events)
- `schema_version` (string)
- `session_id` (string): session identifier, or `unknown` when job-owned or when no harness metadata exists
- `job_id` (string, optional): job identifier for server-mode runs (required when `session_id == "unknown"` in harness runs)
- `ts` (string): RFC3339 timestamp (UTC)
  - audit-derived rows are typically millisecond precision
  - eBPF-derived rows may preserve nanosecond precision from upstream files
- `source` (string): `audit`, `ebpf`, `proxy` (future)
- `event_type` (string): `exec`, `fs_create`, `fs_write`, `fs_rename`, `fs_unlink`, `fs_meta`, `net_summary`, `unix_connect`, `http` (future)
- `pid` (int, optional)
- `ppid` (int, optional)
- `uid` (int, optional)
- `gid` (int, optional)
- `comm` (string, optional)
- `exe` (string, optional)
- `details` (object): source-specific payload

Notes:
- `agent_owned` is not included in the timeline rows. The timeline is intended
  to be the post-filter, owned-by-default view.

## Source-specific details

### audit
Typical keys inside `details`:
- `cmd` (string)
- `cwd` (string)
- `path` (string)
- `audit_seq` (int)
- `audit_key` (string)

### ebpf
Typical keys inside `details`:
- `net` (object)
- `unix` (object)
- `cgroup_id` (string)
- `syscall_result` (int)
- `cmd` (string, optional)

### ebpf (net_summary)
When the merger consumes `filtered_ebpf_summary.jsonl`, network activity is summarized into
`net_summary` rows. These rows represent **send bursts** (split by idle gaps) instead of
raw `net_connect` / `net_send` / DNS events.

Typical keys inside `details` for `net_summary`:
- `dst_ip` (string)
- `dst_port` (int)
- `protocol` (string)
- `dns_names` (array) - DNS answers observed **within the burst window + lookback**
- `connect_count` (int) - `net_connect` events within the burst window
- `send_count` (int)
- `bytes_sent_total` (int)
- `ts_first` (string)
- `ts_last` (string)
- (bursts can be suppressed via `min_send_count` + `min_bytes_sent_total` in `ebpf_summary.yaml`)

### proxy (future)
Typical keys inside `details`:
- `method` (string)
- `url` (string)
- `status` (int)
- `host` (string)
- `port` (int)

## Ordering
The merger outputs rows sorted by:
1) `ts`
2) `source`
3) `pid`

## Examples

### Exec
```json
{
  "schema_version": "timeline.filtered.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:16:46.927Z",
  "source": "audit",
  "event_type": "exec",
  "pid": 1037,
  "ppid": 956,
  "uid": 1001,
  "gid": 1001,
  "comm": "bash",
  "exe": "/usr/bin/bash",
  "details": {
    "cmd": "pwd",
    "cwd": "/work",
    "exec_success": true,
    "exec_exit": 0,
    "audit_seq": 353,
    "audit_key": "exec"
  }
}
```

### File create
```json
{
  "schema_version": "timeline.filtered.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:17:24.214Z",
  "source": "audit",
  "event_type": "fs_create",
  "pid": 1123,
  "ppid": 956,
  "uid": 1001,
  "gid": 1001,
  "comm": "bash",
  "exe": "/usr/bin/bash",
  "details": {
    "path": "/work/temp.txt",
    "audit_seq": 475,
    "audit_key": "fs_watch",
    "cmd": "printf '%s\n' 'hello world' > temp.txt"
  }
}
```

### Network summary
```json
{
  "schema_version": "timeline.filtered.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:16:30.535Z",
  "source": "ebpf",
  "event_type": "net_summary",
  "pid": 956,
  "ppid": 943,
  "uid": 1001,
  "gid": 1001,
  "comm": "tokio-runtime-w",
  "details": {
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
}
```
