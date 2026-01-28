# UI API (Zero-Build Prototype)

This API is the minimal contract for the zero-build UI. It is served by a tiny
HTTP server colocated with the UI static files. No authentication is required
for the local-only prototype.

## Base
- Same origin as the UI (e.g., `http://localhost:8090`).
- All responses are JSON.
- Error responses use `{ "error": "message" }` with appropriate status codes.

## GET /api/timeline
Returns filtered timeline rows from `logs/filtered_timeline.jsonl`.

### Query params (all optional)
- `start`: RFC3339 timestamp (UTC) inclusive.
- `end`: RFC3339 timestamp (UTC) inclusive.
- `limit`: integer; if set, returns only the last N rows in the filtered set.
- `session_id`: filter by session id.
- `job_id`: filter by job id.
- `source`: comma-separated list (`audit,ebpf`).
- `event_type`: comma-separated list (`exec,fs_create,fs_unlink,fs_meta,net_connect,net_send,dns_query,dns_response,unix_connect`).

### Response
```json
{
  "rows": [
    {
      "schema_version": "timeline.filtered.v1",
      "session_id": "session_20260122_001630_de71",
      "job_id": "job_20260128_204429_9680",
      "ts": "2026-01-28T20:44:29.887Z",
      "source": "ebpf",
      "event_type": "net_connect",
      "pid": 4566,
      "ppid": 4562,
      "uid": 1001,
      "gid": 1001,
      "comm": "curl",
      "details": {
        "net": {
          "dst_ip": "104.18.27.120",
          "dst_port": 443
        }
      }
    }
  ],
  "count": 1
}
```

## GET /api/sessions
Returns session metadata from `logs/sessions/*/meta.json`.

### Response
```json
{
  "sessions": [
    {
      "session_id": "session_20260122_001630_de71",
      "mode": "tui",
      "command": "codex -C /work -s danger-full-access",
      "started_at": "2026-01-22T00:16:30.250227+00:00",
      "ended_at": "2026-01-22T00:17:47.384702+00:00",
      "exit_code": 0
    }
  ]
}
```

## GET /api/jobs
Returns job metadata from `logs/jobs/*/input.json` and `status.json`.

### Response
```json
{
  "jobs": [
    {
      "job_id": "job_20260128_204429_9680",
      "status": "complete",
      "prompt": "pwd; printf 'hello world' > /work/temp.txt",
      "command": "bash -lc {prompt}",
      "cwd": "/work",
      "submitted_at": "2026-01-28T20:44:29.577915+00:00",
      "started_at": "2026-01-28T20:44:29.579231+00:00",
      "ended_at": "2026-01-28T20:44:29.981395+00:00",
      "exit_code": 0
    }
  ]
}
```

## GET /api/summary (optional)
Returns event counts for the current filtered view. Use the same query params
as `/api/timeline`.

### Response
```json
{
  "counts": {
    "exec": 12,
    "fs_create": 2,
    "fs_unlink": 1,
    "fs_meta": 1,
    "net_connect": 3,
    "net_send": 1,
    "dns_query": 2,
    "dns_response": 2,
    "unix_connect": 4
  },
  "total": 28
}
```
