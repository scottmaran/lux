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
- `source`: comma-separated list (`audit,ebpf,proxy`).
- `event_type`: comma-separated list (`exec,fs_create,fs_unlink,fs_meta,net_summary,unix_connect,http`).

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
      "event_type": "net_summary",
      "pid": 4566,
      "ppid": 4562,
      "uid": 1001,
      "gid": 1001,
      "comm": "curl",
      "details": {
        "dst_ip": "104.18.27.120",
        "dst_port": 443,
        "dns_names": ["chatgpt.com"],
        "connect_count": 1,
        "send_count": 3,
        "bytes_sent_total": 1200
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
      "name": "TUI debug run",
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
      "name": "Quick filesystem check",
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

## PATCH /api/sessions/<id>
Updates the display name for a session using label files under `logs/labels/sessions/`.

### Request body
```json
{ "name": "Readable session name" }
```

### Response
```json
{
  "id": "session_20260122_001630_de71",
  "name": "Readable session name",
  "updated_at": "2026-02-02T21:44:29.981395+00:00"
}
```

## PATCH /api/jobs/<id>
Updates the display name for a job using label files under `logs/labels/jobs/`.

### Request body
```json
{ "name": "Readable job name" }
```

### Response
```json
{
  "id": "job_20260128_204429_9680",
  "name": "Readable job name",
  "updated_at": "2026-02-02T21:44:29.981395+00:00"
}
```

## GET /api/summary (optional)
Returns event counts for the current filtered view. Use the same query params
as `/api/timeline`.

The current UI derives summary tiles from this data:
- **Processes**: `exec`
- **File changes**: `fs_create + fs_unlink + fs_meta`
- **Network calls**: `net_summary`
- **HTTP requests**: `http`

### Response
```json
{
  "counts": {
    "exec": 12,
    "fs_create": 2,
    "fs_unlink": 1,
    "fs_meta": 1,
    "net_summary": 3,
    "http": 5,
    "unix_connect": 4
  },
  "total": 28
}
```
