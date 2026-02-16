# Runtime Control Plane
Layer: Contract

The runtime control-plane is a local Unix-socket HTTP service used by CLI and
UI for lifecycle, health, and evidence-state visibility.

## Transport And Auth

- Transport: HTTP over Unix domain socket.
- Default socket path: `<config_dir>/runtime/control_plane.sock`.
- Auth model: filesystem permissions on runtime dir/socket.
  - Runtime dir: `0770`
  - Socket file: `0660`
  - Owner uid: invoking user
  - Group: `runtime_control_plane.socket_gid` (or invoking primary gid)

## Lifecycle

- Start daemon: `lasso runtime up`
- Stop daemon: `lasso runtime down`
- Check daemon: `lasso runtime status`
- Normal CLI lifecycle commands auto-start runtime when unavailable.

## Endpoints

### GET `/v1/stack/status`

Returns current runtime + stack summary.

```json
{
  "runtime": {
    "socket_path": "/Users/me/.config/lasso/runtime/control_plane.sock",
    "auto_started": true
  },
  "stack": {
    "collector_running": true,
    "provider_running": true,
    "ui_running": false,
    "rotation_pending": false,
    "active_run_id": "lasso__2026_02_16_17_01_02"
  }
}
```

### GET `/v1/run/status`

Returns active-run pointer and rotation state.

### GET `/v1/session-job/status`

Returns active run id and session/job counts.

### GET `/v1/collector/pipeline/status`

Returns pipeline file presence/size/mtime for active run.

### GET `/v1/warnings`

Returns recent runtime warnings and recent error-severity events.

### GET `/v1/events`

Server-Sent Events stream.

- Supports replay from id via:
  - header: `Last-Event-ID`
  - query: `?last_event_id=<n>`
- Events are ordered by monotonically increasing `id`.

### POST `/v1/execute`

CLI lifecycle execution proxy.

Request:

```json
{ "argv": ["up", "--provider", "codex", "--wait"] }
```

Response:

```json
{
  "status_code": 0,
  "stdout": "{...}",
  "stderr": ""
}
```

### POST `/v1/runtime/down`

Requests runtime daemon shutdown.

## Event Envelope

Each event on `/v1/events` follows:

```json
{
  "id": 42,
  "ts": "2026-02-16T17:24:20.235Z",
  "event_type": "run.started",
  "severity": "info",
  "payload": {}
}
```

Required fields:
- `id`: monotonically increasing integer
- `ts`: RFC3339 timestamp
- `event_type`: lifecycle/degradation/attribution semantic type
- `severity`: `info|warn|error`
- `payload`: object

## UI Proxy Contract

`ui/server.py` exposes same-origin runtime routes and proxies to this API:

- `/api/runtime/stack-status` -> `/v1/stack/status`
- `/api/runtime/run-status` -> `/v1/run/status`
- `/api/runtime/session-job-status` -> `/v1/session-job/status`
- `/api/runtime/collector-pipeline-status` -> `/v1/collector/pipeline/status`
- `/api/runtime/warnings` -> `/v1/warnings`
- `/api/runtime/events` -> `/v1/events` (SSE passthrough with replay headers)
