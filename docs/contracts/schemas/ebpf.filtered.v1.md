# eBPF Filtered Data Schema (`ebpf.filtered.v1`)
Layer: Contract

This document defines the JSONL emitted by the eBPF filter stage
(`collector-ebpf-filter`), which attributes raw eBPF events to a session/job
owner and optionally links events back to the originating command.

Where it shows up:
- In a run-scoped deployment, this file is typically
  `<log_root>/<run_id>/collector/filtered/filtered_ebpf.jsonl`.
- The exact path is controlled by `COLLECTOR_EBPF_FILTER_OUTPUT`.

Upstream and downstream:
- Raw input schema: `docs/contracts/schemas/ebpf.raw.md` (`ebpf.v1`, `ebpf.jsonl`)
- Summary schema: `docs/contracts/schemas/ebpf.summary.v1.md` (`ebpf.summary.v1`, `filtered_ebpf_summary.jsonl`)

## Row format
- The file is JSONL (one JSON object per line).
- Each line is one event attributed to an owner (best-effort).

## Ownership and attribution
- Rows are emitted only for events the filter considers agent-owned.
  - `agent_owned` is always `true` for emitted rows.
- `session_id` and `job_id` attribution is best-effort:
  - In harness runs, rows should be attributable to either a real `session_id`,
    or to a job via `job_id` with `session_id="unknown"`.
  - In collector-only runs (no harness metadata), `session_id` can remain
    `"unknown"` with no `job_id`.
- Attribution semantics and precedence are documented in
  `docs/contracts/attribution.md`.

## Common fields (all event types)
Required unless noted.

- `schema_version` (string): fixed `ebpf.filtered.v1`
- `session_id` (string): harness session id, or `"unknown"`
- `job_id` (string, optional): present only for job-owned rows
- `ts` (string): RFC3339 timestamp (typically nanosecond precision, sourced from the raw eBPF event)
- `source` (string): fixed `ebpf`
- `event_type` (string): one of the event types below
- `pid` (int)
- `ppid` (int)
- `uid` (int)
- `gid` (int)
- `comm` (string): kernel comm (may be empty)
- `cgroup_id` (string): kernel cgroup id in hex (`0x...`)
- `syscall_result` (int): raw syscall return value
- `agent_owned` (bool): always `true` for emitted rows
- `cmd` (string, optional): best-effort originating command (when enabled by config)

## Event types and payloads
The filter retains the raw event types:
- `net_connect`
- `net_send`
- `dns_query`
- `dns_response`
- `unix_connect`

Payload fields match the raw schema:
- `net_connect` / `net_send` include a `net` object
- `dns_query` / `dns_response` include a `dns` object
- `unix_connect` includes a `unix` object

## Examples

### unix_connect (attributed)
```json
{
  "schema_version": "ebpf.filtered.v1",
  "session_id": "session_20260128_200000_ab12",
  "ts": "2026-01-28T20:00:01.500000000Z",
  "source": "ebpf",
  "event_type": "unix_connect",
  "pid": 5090,
  "ppid": 5080,
  "uid": 1001,
  "gid": 1001,
  "comm": "codex",
  "cgroup_id": "0x0000000000000abc",
  "syscall_result": 0,
  "agent_owned": true,
  "cmd": "codex -C /work -s danger-full-access",
  "unix": {
    "path": "/run/dbus/system_bus_socket",
    "abstract": false,
    "sock_type": "stream"
  }
}
```

### dns_query (job-owned)
```json
{
  "schema_version": "ebpf.filtered.v1",
  "session_id": "unknown",
  "job_id": "job_20260128_200500_cd34",
  "ts": "2026-01-28T20:05:01.200000000Z",
  "source": "ebpf",
  "event_type": "dns_query",
  "pid": 6090,
  "ppid": 6080,
  "uid": 1001,
  "gid": 1001,
  "comm": "codex",
  "cgroup_id": "0x0000000000000def",
  "syscall_result": 0,
  "agent_owned": true,
  "cmd": "codex -C /work -s danger-full-access exec",
  "dns": {
    "transport": "udp",
    "query_name": "example.com",
    "query_type": "A",
    "server_ip": "127.0.0.11",
    "server_port": 53
  }
}
```
