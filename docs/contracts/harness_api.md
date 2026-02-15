# Harness HTTP API (Server Mode)
Layer: Contract

This API is served by `harness/harness.py` when running in `server` mode.

Auth:
- All requests must include header `X-Harness-Token` matching `HARNESS_API_TOKEN`.
- If `HARNESS_API_TOKEN` is unset, the server refuses to start.

Important limitation:
- `GET /jobs/<id>` returns in-memory job state only; the harness does not load
  historical jobs from disk after a restart.

## POST /run
Submit a non-interactive job that will run inside the agent container over SSH.

Request body (JSON object):
- `prompt` (string, required): the prompt text passed to the configured
  `HARNESS_RUN_CMD_TEMPLATE`.
- `capture_input` (bool, optional; default `true`): if `false`, the persisted
  `input.json` contains `"[redacted]"` instead of the prompt text.
- `cwd` (string, optional): absolute path under `HARNESS_AGENT_WORKDIR`.
  Invalid/unsafe values are ignored and the default is used.
- `env` (object, optional): environment variables for the remote command.
  Keys are sanitized; values are stringified. This map is persisted in job
  metadata by design.
- `timeout_sec` (number, optional): if set to `> 0`, applies both a remote
  `timeout` wrapper and a local wait/kill bound.
- `name` (string, optional): human-friendly label for UI; written under
  `labels/jobs/<job_id>.json`.

Responses:
- `202`: accepted.
- `400`: invalid request (for example missing/empty `prompt`, invalid JSON).
- `401`: unauthorized (missing/incorrect `X-Harness-Token`).
- `404`: not found (wrong path).

Example request:
```json
{
  "prompt": "pwd; printf 'ok' > /work/out.txt",
  "cwd": "/work",
  "env": { "FOO": "bar" },
  "timeout_sec": 120,
  "capture_input": true,
  "name": "Quick smoke"
}
```

Example response (`202`):
```json
{
  "job_id": "job_20260214_155736_d16e",
  "status": "queued",
  "submitted_at": "2026-02-14T15:57:36.086910+00:00",
  "name": "Quick smoke"
}
```

Notes:
- The returned `job_id` is the canonical identifier for on-disk artifacts under
  `jobs/<job_id>/...` (see `docs/contracts/harness_artifacts.md`).
- `root_pid`/`root_sid` are captured asynchronously and may not appear
  immediately in status.

## GET /jobs/<id>
Return in-memory status for a submitted job.

Responses:
- `200`: job exists in memory; returns a JSON object with status and artifact
  paths.
- `401`: unauthorized.
- `404`: unknown job id (or the harness restarted and lost in-memory state).

Example response (`200`):
```json
{
  "job_id": "job_20260214_155736_d16e",
  "status": "complete",
  "submitted_at": "2026-02-14T15:57:36.086910+00:00",
  "started_at": "2026-02-14T15:57:36.100000+00:00",
  "ended_at": "2026-02-14T15:57:37.200000+00:00",
  "exit_code": 0,
  "error": null,
  "output_path": "/logs/<run_id>/harness/jobs/<job_id>/stdout.log",
  "error_path": "/logs/<run_id>/harness/jobs/<job_id>/stderr.log",
  "filtered_timeline_path": "/logs/<run_id>/harness/jobs/<job_id>/filtered_timeline.jsonl",
  "root_pid": 1234,
  "root_sid": 1234
}
```

