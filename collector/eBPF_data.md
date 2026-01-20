# eBPF Data Schema (v1)

This document defines the minimal event set and JSON schema for the custom eBPF
collector output. Events are emitted as JSONL (one JSON object per line).

## Scope (minimal event set)
The loader emits five event types:
- `net_connect` (TCP connect attempts)
- `net_send` (UDP sendto/sendmsg egress)
- `dns_query` (DNS request over UDP/TCP port 53)
- `dns_response` (DNS response over UDP/TCP port 53)
- `unix_connect` (Unix domain socket connect, including D-Bus)

Payload content is never captured. Only metadata is emitted.

## Common fields (all events)
Fields are lower snake_case. Required unless marked optional.

- `schema_version` (string): Fixed value `ebpf.v1`.
- `ts` (string): RFC3339Nano timestamp of the event.
- `event_type` (string): One of the five event types above.
- `pid` (int): Process ID.
- `ppid` (int): Parent process ID.
- `uid` (int): User ID.
- `gid` (int): Group ID.
- `comm` (string): Process name (kernel comm, truncated).
- `cgroup_id` (string): Kernel cgroup ID in hex (e.g. `0x1234abcd`).
- `syscall_result` (int): Raw syscall return value.

`syscall_result` semantics:
- `net_connect`: `0` on success, negative errno on failure.
- `net_send`: number of bytes sent on success, negative errno on failure.
- `dns_*`/`unix_connect`: `0` on success, negative errno on failure.

## Event payloads

### net_connect
```json
{
  "schema_version": "ebpf.v1",
  "ts": "2025-01-19T20:57:34.123456789Z",
  "event_type": "net_connect",
  "pid": 1234,
  "ppid": 567,
  "uid": 1000,
  "gid": 1000,
  "comm": "curl",
  "cgroup_id": "0x0000000000000000",
  "syscall_result": 0,
  "net": {
    "protocol": "tcp",
    "family": "ipv4",
    "src_ip": "192.0.2.10",
    "src_port": 54321,
    "dst_ip": "93.184.216.34",
    "dst_port": 443
  }
}
```

### net_send
```json
{
  "schema_version": "ebpf.v1",
  "ts": "2025-01-19T20:57:35.123456789Z",
  "event_type": "net_send",
  "pid": 1234,
  "ppid": 567,
  "uid": 1000,
  "gid": 1000,
  "comm": "dig",
  "cgroup_id": "0x0000000000000000",
  "syscall_result": 42,
  "net": {
    "protocol": "udp",
    "family": "ipv4",
    "src_ip": "192.0.2.10",
    "src_port": 5353,
    "dst_ip": "8.8.8.8",
    "dst_port": 53,
    "bytes": 42
  }
}
```

### dns_query
```json
{
  "schema_version": "ebpf.v1",
  "ts": "2025-01-19T20:57:36.123456789Z",
  "event_type": "dns_query",
  "pid": 1234,
  "ppid": 567,
  "uid": 1000,
  "gid": 1000,
  "comm": "dig",
  "cgroup_id": "0x0000000000000000",
  "syscall_result": 0,
  "dns": {
    "transport": "udp",
    "query_name": "example.com",
    "query_type": "A",
    "server_ip": "8.8.8.8",
    "server_port": 53
  }
}
```

### dns_response
```json
{
  "schema_version": "ebpf.v1",
  "ts": "2025-01-19T20:57:36.223456789Z",
  "event_type": "dns_response",
  "pid": 1234,
  "ppid": 567,
  "uid": 1000,
  "gid": 1000,
  "comm": "dig",
  "cgroup_id": "0x0000000000000000",
  "syscall_result": 0,
  "dns": {
    "transport": "udp",
    "query_name": "example.com",
    "query_type": "A",
    "rcode": "NOERROR",
    "answers": ["93.184.216.34"]
  }
}
```

### unix_connect
```json
{
  "schema_version": "ebpf.v1",
  "ts": "2025-01-19T20:57:37.123456789Z",
  "event_type": "unix_connect",
  "pid": 1234,
  "ppid": 567,
  "uid": 1000,
  "gid": 1000,
  "comm": "dbus-daemon",
  "cgroup_id": "0x0000000000000000",
  "syscall_result": 0,
  "unix": {
    "path": "/run/dbus/system_bus_socket",
    "abstract": false,
    "sock_type": "stream"
  }
}
```

## Notes and constraints
- DNS parsing covers UDP and TCP on port 53 via send/recv syscalls; DoH/DoT traffic is not decoded.
- `src_ip`/`src_port` and unix `sock_type` are resolved in userspace from `/proc` when possible.
- `exe` is omitted.
- `cgroup_id` is retained for correlation; mapping to container IDs happens later in the merger.
