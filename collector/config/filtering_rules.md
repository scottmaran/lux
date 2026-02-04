# Auditd Filtering Rules

This document explains the filtering configuration in
`collector/config/filtering.yaml` and why each field is configurable.

## Purpose
- Input: raw auditd logs.
- Output: compact JSONL timeline used by the UI (see `docs/ui/UI_DESIGN.md`).
- Schema and event meanings live in `collector/auditd_data.md`.

## Why a config file
- Environments differ (UIDs, paths, shells).
- Noise vs. signal is use-case dependent.
- We may change grouping or attribution strategy without rewriting code.

## Config fields

schema_version
- Output schema version to emit (currently `auditd.filtered.v1`).
- Configurable so the filter can emit/validate different schema versions.

input.audit_log
- Path to the raw auditd log.
- Configurable for different mount layouts or test fixtures.

sessions_dir
- Directory containing session metadata (`logs/sessions/*/meta.json`).
- Used to map audit events to a `session_id` based on time windows.

jobs_dir
- Directory containing job metadata (`logs/jobs/*/input.json`, `status.json`).
- Used to map audit events to `job_id` based on time windows.

output.jsonl
- Path to the filtered JSONL output.
- Configurable for different log sinks or test output folders.

grouping.strategy
- How to collapse multi-record audit events.
- Current value `audit_seq` uses the `msg=audit(...:<seq>)` sequence.
- Configurable so we can swap strategies if we ingest from other sources.

agent_ownership.uid
- Default UID for the agent user (e.g., 1001).
- Configurable because images/users can use different UIDs.

agent_ownership.root_comm
- Process names considered a session root (e.g., `codex`).
- Used to anchor the agent-owned process tree so unrelated UID-matching
  processes do not leak into the filtered log.
- This is a pragmatic fallback until we wire in root PID or cgroup ID.

exec.include_keys
- Audit rule keys that represent exec events (default `exec`).
- Configurable so rule key changes do not require code changes.

exec.shell_comm
- Process names treated as shells (`bash`, `sh`, etc.).
- Configurable because some environments use `zsh`, `dash`, or `busybox`.

exec.shell_cmd_flag
- Flag used to extract the "real" command from a shell (`-lc` by default).
- Configurable because some harnesses use `-c` or other flags.

exec.helper_exclude_comm
- Process names to suppress as helper/noise.
- Needed because `exec` captures all process launches, not just agent intent.

exec.helper_exclude_argv_prefix
- More specific suppression based on argv prefixes.
- Example: drop `git rev-parse` probes while allowing other `git` commands.

fs.include_keys
- Audit rule keys that represent filesystem events (`fs_watch`, `fs_change`,
  `fs_meta`).
- Configurable to align with rule changes.

fs.include_paths_prefix
- Only include filesystem events under these path prefixes.
- Configurable to match different workspace mounts.

linking.attach_cmd_to_fs
- Whether to attach the originating command to file events.
- Useful for readability, but optional if you prefer strict raw attribution.

linking.attach_cmd_strategy
- How to attach commands to file events (e.g., `last_exec_same_pid`).
- Configurable so we can experiment with better attribution heuristics.
