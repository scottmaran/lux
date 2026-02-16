# UI API
Layer: Contract

This API is the minimal contract for the Lasso UI. It is served by a tiny HTTP
server colocated with the UI static files. No authentication is required for
the local-only UI.

## Base
- Same origin as the UI (e.g., `http://localhost:8090`).
- All responses are JSON.
- Error responses use `{ "error": "message" }` with appropriate status codes.
- Default run selection uses `<log_root>/.active_run.json`.
- `lasso up` manages active-run state automatically.
- In manual `docker compose` workflows, keep a shared `LASSO_RUN_ID` across collector/harness runs and write `.active_run.json`, or pass `?run_id=<id>` explicitly in API calls.

## GET /api/timeline
Returns filtered timeline rows from
`<log_root>/<run_id>/collector/filtered/filtered_timeline.jsonl`.
Defaults to the active run when `run_id` is not provided.

### Query params (all optional)
- `start`: RFC3339 timestamp (UTC) inclusive.
- `end`: RFC3339 timestamp (UTC) inclusive.
- `limit`: integer; if set, returns only the last N rows in the filtered set.
- `run_id`: explicit run directory id (example: `lasso__2026_02_12_12_23_54`).
- `session_id`: filter by session id.
- `job_id`: filter by job id.
- `source`: comma-separated list (`audit,ebpf`).
- `event_type`: comma-separated list (`exec,fs_create,fs_write,fs_rename,fs_unlink,fs_meta,net_summary,unix_connect`).

### Response
```json
{
  "run_id": "lasso__2026_02_12_12_23_54",
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
Returns session metadata from `<log_root>/<run_id>/harness/sessions/*/meta.json`.
Defaults to active run; supports `?run_id=<id>`.

### Response
```json
{
  "run_id": "lasso__2026_02_12_12_23_54",
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
Returns job metadata from `<log_root>/<run_id>/harness/jobs/*/input.json` and
`status.json`. Defaults to active run; supports `?run_id=<id>`.

### Response
```json
{
  "run_id": "lasso__2026_02_12_12_23_54",
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

## GET /api/runs
Returns discovered run directories and the active run id.

### Response
```json
{
  "runs": ["lasso__2026_02_12_12_23_54", "lasso__2026_02_13_07_14_32"],
  "active_run_id": "lasso__2026_02_13_07_14_32"
}
```

## PATCH /api/sessions/<id>
Updates the display name for a session using label files under
`<log_root>/<run_id>/harness/labels/sessions/`.
Defaults to active run; supports `?run_id=<id>`.

### Request body
```json
{ "name": "Readable session name" }
```

### Response
```json
{
  "run_id": "lasso__2026_02_12_12_23_54",
  "id": "session_20260122_001630_de71",
  "name": "Readable session name",
  "updated_at": "2026-02-02T21:44:29.981395+00:00"
}
```

## PATCH /api/jobs/<id>
Updates the display name for a job using label files under
`<log_root>/<run_id>/harness/labels/jobs/`.
Defaults to active run; supports `?run_id=<id>`.

### Request body
```json
{ "name": "Readable job name" }
```

### Response
```json
{
  "run_id": "lasso__2026_02_12_12_23_54",
  "id": "job_20260128_204429_9680",
  "name": "Readable job name",
  "updated_at": "2026-02-02T21:44:29.981395+00:00"
}
```

## GET /api/summary (optional)
Returns event counts for the current filtered view. Use the same query params
as `/api/timeline`.

The current UI derives three summary tiles from this data:
- **Processes**: `exec`
- **File changes**: `fs_create + fs_unlink + fs_meta`
- **Network calls**: `net_summary`

### Response
```json
{
  "run_id": "lasso__2026_02_12_12_23_54",
  "counts": {
    "exec": 12,
    "fs_create": 2,
    "fs_unlink": 1,
    "fs_meta": 1,
    "net_summary": 3,
    "unix_connect": 4
  },
  "total": 28
}
```
