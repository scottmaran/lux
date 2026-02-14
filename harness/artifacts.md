# Harness Artifacts (On-Disk Contract)

This document describes the files the harness writes under `HARNESS_LOG_DIR`.

In run-scoped deployments, `compose.yml` sets:
- `HARNESS_LOG_DIR=/logs/${LASSO_RUN_ID}/harness`

## Directory Layout
```text
<HARNESS_LOG_DIR>/
  sessions/
    <session_id>/
      meta.json
      stdin.log
      stdout.log
      filtered_timeline.jsonl
  jobs/
    <job_id>/
      input.json
      status.json
      stdout.log
      stderr.log
      filtered_timeline.jsonl
  labels/
    sessions/
      <session_id>.json
    jobs/
      <job_id>.json
```

## Sessions
Path: `sessions/<session_id>/...`

### `meta.json`
Written by `harness/harness.py` (TUI path).

Fields (best-effort; some are written after the session ends):
- `session_id` (string)
- `started_at` (string, RFC3339)
- `ended_at` (string, RFC3339, optional)
- `mode` (string): `tui`
- `command` (string): `HARNESS_TUI_CMD` value
- `exit_code` (int, optional)
- `stdin_path` (string, optional)
- `stdout_path` (string, optional)
- `filtered_timeline_path` (string, optional)
- `root_pid` (int, optional): captured asynchronously
- `root_sid` (int, optional): captured asynchronously

### `stdin.log` / `stdout.log`
- Raw byte logs of the interactive PTY session.
- Not guaranteed to be line-oriented.

### `filtered_timeline.jsonl`
- A derived snapshot containing only merged timeline rows whose `session_id`
  matches this session.
- Materialized by filtering `HARNESS_TIMELINE_PATH` (see `harness/README.md` for
  reconcile semantics).

## Jobs
Path: `jobs/<job_id>/...`

### `input.json`
Written at job start by `harness/harness.py`.

Fields:
- `job_id` (string)
- `submitted_at` (string, RFC3339)
- `started_at` (string, RFC3339)
- `prompt` (string): the prompt (or `"[redacted]"` if `capture_input=false`)
- `cwd` (string)
- `env` (object): persisted by design (keys sanitized, values stringified)
- `command` (string): the raw `HARNESS_RUN_CMD_TEMPLATE` value
- `root_pid` (int, optional): captured asynchronously
- `root_sid` (int, optional): captured asynchronously

### `status.json`
Written at job end (and sometimes updated later with markers).

Fields:
- `job_id` (string)
- `status` (string): `queued`, `running`, `complete`, `failed`
- `submitted_at` (string, RFC3339)
- `started_at` (string, RFC3339, optional)
- `ended_at` (string, RFC3339, optional)
- `exit_code` (int, optional)
- `error` (string|null)
- `output_path` (string|null): container path to `stdout.log`
- `error_path` (string|null): container path to `stderr.log`
- `filtered_timeline_path` (string|null): container path to `filtered_timeline.jsonl`
- `root_pid` (int|null): captured asynchronously
- `root_sid` (int|null): captured asynchronously

### `stdout.log` / `stderr.log`
- Raw byte logs of the remote non-interactive run (SSH stdout/stderr).

### `filtered_timeline.jsonl`
- A derived snapshot containing only merged timeline rows whose `job_id`
  matches this job.

## Labels
Paths:
- `labels/sessions/<session_id>.json`
- `labels/jobs/<job_id>.json`

Shape:
```json
{ "name": "Readable name", "updated_at": "2026-02-14T15:57:36.086910+00:00" }
```

