# `audit_filtering.yaml` (Audit Filter Config)
Layer: Contract

This file configures the auditd filter stage (`collector-audit-filter`), which:
- parses raw `audit.log`,
- groups multi-record events by audit sequence,
- determines agent ownership,
- emits compact `auditd.filtered.v1` JSONL.

File:
- `collector/config/audit_filtering.yaml`

Schema:
- Output schema contract: `docs/contracts/schemas/auditd.filtered.v1.md`

## Runtime wiring (env overrides)
In container runs, `compose.yml` and/or the collector entrypoint can override
config paths and inputs/outputs via env vars:

- `COLLECTOR_FILTER_CONFIG`: config file path
- `COLLECTOR_AUDIT_LOG`: raw audit log path (input)
- `COLLECTOR_FILTER_OUTPUT`: filtered audit JSONL path (output)
- `COLLECTOR_SESSIONS_DIR`: run-scoped sessions metadata directory
- `COLLECTOR_JOBS_DIR`: run-scoped jobs metadata directory
- `COLLECTOR_ROOT_COMM`: comma-separated root comm override (overrides `agent_ownership.root_comm` when set)

Note:
- The shipped YAML defaults can look "flat" (`/logs/...`). In real runs they
  are overridden to run-scoped paths under `/logs/${LASSO_RUN_ID}/...`.

## Why this config exists
Audit environments vary:
- different agent UIDs,
- different shell wrappers (`bash -lc` vs `sh -c`),
- different sources of exec noise.

Keeping these knobs in config makes it easier to tune signal/noise without
rewriting core parsing logic.

## Key fields (current)

`schema_version`
- The schema version string written into each output row (default:
  `auditd.filtered.v1`).

`input.audit_log`
- Path to the raw audit log (often overridden by `COLLECTOR_AUDIT_LOG`).

`sessions_dir` / `jobs_dir`
- Paths to harness metadata directories, used to map events to `session_id` or
  `job_id` based on root PID/SID markers.
- Attribution semantics are documented in `docs/contracts/attribution.md`.

`output.jsonl`
- Output JSONL path (often overridden by `COLLECTOR_FILTER_OUTPUT`).

`grouping.strategy`
- How the filter collapses multi-record audit events.
- Current supported value: `audit_seq` (group by `msg=audit(...:<seq>)`).

`agent_ownership.uid`
- Default UID of the agent user (commonly 1001).

`agent_ownership.root_comm`
- Process names treated as eligible "roots" for agent ownership heuristics.
- This is a pragmatic fallback when harness root markers are unavailable or
  delayed during startup.

`exec.include_keys`
- Audit rule keys treated as exec events (default `exec`).

`exec.shell_comm` / `exec.shell_cmd_flag`
- When a process comm matches a configured shell and the argv contains the
  configured flag (default `-lc`), the filter extracts the inner command string
  for readability.

`exec.helper_exclude_comm` / `exec.helper_exclude_argv_prefix`
- Suppression lists to drop known noise execs (for example `git rev-parse` probes).

`fs.include_keys`
- Audit rule keys treated as filesystem activity (for example `fs_watch`,
  `fs_change`, `fs_meta`).

`fs.include_paths_prefix`
- Only include filesystem events whose derived `path` is under one of these
  prefixes (default `/work/`).

`linking.attach_cmd_to_fs`
- If enabled, the filter attaches a best-effort `cmd` string to fs events by
  reusing the last seen exec `cmd` for the same PID.
