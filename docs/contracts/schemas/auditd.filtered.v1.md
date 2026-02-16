# Auditd Filtered Data Schema (`auditd.filtered.v1`)
Layer: Contract

This document defines the JSONL emitted by the auditd filter stage
(`collector-audit-filter`), which normalizes raw `audit.log` records into
one JSON object per logical event.

Where it shows up:
- In a run-scoped deployment, this file is typically
  `<log_root>/<run_id>/collector/filtered/filtered_audit.jsonl`.
- The exact path is controlled by `COLLECTOR_FILTER_OUTPUT`.

For the raw audit log format, see `docs/contracts/schemas/auditd.raw.md`.

## Row format
- The file is JSONL (one JSON object per line).
- Each line is one normalized event.

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
Required unless noted. Some fields can be `null` depending on what auditd
emitted for that sequence.

- `schema_version` (string): fixed `auditd.filtered.v1`
- `session_id` (string): harness session id, or `"unknown"`
- `job_id` (string, optional): present only for job-owned rows
- `ts` (string): RFC3339 timestamp (UTC, millisecond precision)
- `source` (string): fixed `audit`
- `event_type` (string): one of the event types below
- `pid` (int|null)
- `ppid` (int|null)
- `uid` (int|null)
- `gid` (int|null)
- `comm` (string): kernel comm (may be empty)
- `exe` (string|null): resolved executable path
- `audit_seq` (int): audit sequence number (`msg=audit(...:<seq>)`)
- `audit_key` (string|null): audit rule key (for example `exec`, `fs_watch`, `fs_change`, `fs_meta`)
- `agent_owned` (bool): always `true` for emitted rows

## Event types
The filter currently emits:
- `exec`
- `fs_create`
- `fs_write`
- `fs_rename`
- `fs_unlink`
- `fs_meta`

### `exec`
Additional fields:
- `cmd` (string): derived command string
  - For shell execs (for example `bash -lc <cmd>`), the filter extracts the
    inner command payload from the configured shell flag (default `-lc`).
  - Otherwise `cmd` is a shell-escaped join of argv (`shlex.join(argv)`).
- `cwd` (string|null): current working directory when available
- `exec_success` (bool, optional): `true` on success, `false` on failure
- `exec_exit` (int, optional): raw syscall return value (negative errno on failure)
- `exec_errno_name` (string, optional): errno name derived from `exec_exit` (for failures)
- `exec_attempted_path` (string, optional): best-effort attempted path from PATH records

### Filesystem events: `fs_*`
Additional fields:
- `path` (string): selected path derived from PATH records
- `cwd` (string|null): current working directory when available
- `cmd` (string, optional): attached originating command, if enabled by config

Notes:
- `event_type` is derived from PATH `nametype` values and/or the audit rule key:
  - CREATE+DELETE in the same seq => `fs_rename`
  - CREATE only => `fs_create`
  - DELETE only => `fs_unlink`
  - audit_key `fs_meta` => `fs_meta`
  - otherwise => `fs_write`
- `audit_key` distinguishes which audit rule matched (for example `fs_watch` vs
  `fs_change`), even when the derived `event_type` is the same.

## Examples

### Exec
```json
{
  "schema_version": "auditd.filtered.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:16:46.927Z",
  "source": "audit",
  "event_type": "exec",
  "cmd": "pwd",
  "cwd": "/work",
  "comm": "bash",
  "exe": "/usr/bin/bash",
  "pid": 1037,
  "ppid": 956,
  "uid": 1001,
  "gid": 1001,
  "audit_seq": 353,
  "audit_key": "exec",
  "agent_owned": true,
  "exec_success": true,
  "exec_exit": 0
}
```

### File create (with `cmd` linking enabled)
```json
{
  "schema_version": "auditd.filtered.v1",
  "session_id": "session_20260122_001630_de71",
  "ts": "2026-01-22T00:17:24.214Z",
  "source": "audit",
  "event_type": "fs_create",
  "path": "/work/temp.txt",
  "cwd": "/work",
  "cmd": "printf '%s\\n' 'hello world' > temp.txt",
  "comm": "bash",
  "exe": "/usr/bin/bash",
  "pid": 1123,
  "ppid": 956,
  "uid": 1001,
  "gid": 1001,
  "audit_seq": 475,
  "audit_key": "fs_watch",
  "agent_owned": true
}
```
