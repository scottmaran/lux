# Timeline Data Schema (v1)

This document defines the unified, filtered timeline emitted by the merger.
The UI should consume this file rather than raw audit/eBPF logs.

## Schema version
- `schema_version`: fixed `timeline.filtered.v1`

## Common fields (all events)
- `schema_version` (string)
- `session_id` (string): session identifier, or `unknown`
- `job_id` (string, optional): job identifier for server-mode runs
- `ts` (string): RFC3339 timestamp (UTC, millisecond precision)
- `source` (string): `audit`, `ebpf`, `proxy` (future)
- `event_type` (string): `exec`, `fs_create`, `fs_unlink`, `fs_meta`, `net_connect`, `net_send`, `dns_query`, `dns_response`, `unix_connect`, `http` (future)
- `pid` (int, optional)
- `ppid` (int, optional)
- `uid` (int, optional)
- `gid` (int, optional)
- `comm` (string, optional)
- `exe` (string, optional)
- `details` (object): source-specific payload

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
- `dns` (object)
- `unix` (object)
- `cgroup_id` (string)
- `syscall_result` (int)
- `cmd` (string, optional)

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

### Network connect
```json
{
  "schema_version": "timeline.filtered.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:16:30.535Z",
  "source": "ebpf",
  "event_type": "net_connect",
  "pid": 956,
  "ppid": 943,
  "uid": 1001,
  "gid": 1001,
  "comm": "tokio-runtime-w",
  "details": {
    "net": {
      "protocol": "tcp",
      "family": "ipv4",
      "src_ip": "172.18.0.3",
      "src_port": 46420,
      "dst_ip": "104.18.32.47",
      "dst_port": 443
    },
    "cgroup_id": "0x0000000000000270",
    "syscall_result": -115
  }
}
```

### DNS query
```json
{
  "schema_version": "timeline.filtered.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:16:30.533Z",
  "source": "ebpf",
  "event_type": "dns_query",
  "pid": 956,
  "ppid": 943,
  "uid": 1001,
  "gid": 1001,
  "comm": "tokio-runtime-w",
  "details": {
    "dns": {
      "transport": "udp",
      "query_name": "chatgpt.com",
      "query_type": "A",
      "server_ip": "127.0.0.11",
      "server_port": 53
    }
  }
}
```
