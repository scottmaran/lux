# Testing Guide

This document describes how to validate the audit pipeline and the audit
filter behavior.

## Test Layers

- Collector smoke tests (raw auditd + eBPF logs).
- Integration tests for harness + agent workflows.
- Audit filter tests (spec-driven, implemented).
- eBPF filter tests (spec-driven, pending implementation).
- Unified merge tests (spec-driven, pending implementation).
- Unit tests with fixture logs for deterministic parsing.

## Integration Tests (Quick Start)

### Stub (no Codex required)
```bash
export HARNESS_API_TOKEN=dev-token
export HARNESS_RUN_CMD_TEMPLATE='echo stub-ok'
./scripts/run_integration_stub.sh
```

### Codex
Requires `~/.codex/auth.json` and `~/.codex/skills` on the host.
```bash
export HARNESS_API_TOKEN=dev-token
./scripts/run_integration_codex.sh
```

## Collector Smoke Test (raw logs)

Script: `collector/scripts/run_test.sh`

What it does:
- Builds the collector image.
- Runs the collector with privileged mounts.
- Generates filesystem activity in `/work`.
- Generates network + unix socket activity.
- Prints log summary and tail output.

Expected:
- `logs/audit.log` grows and contains exec + fs entries.
- `logs/ebpf.jsonl` grows and contains net/unix entries.

This is a raw pipeline check; it does not validate filtering.

## Audit Filter Test Cases

These cases validate the filter logic once implemented. Because `exec` includes
the `codex` runtime, counts are minimums rather than exact values.

Case A: agent + collector only (no harness)
- Setup: start agent + collector containers, no Codex run.
- Expected: 0 filtered rows (no agent-owned root process).

Case B: non-interactive job (server mode)
- Prompt: "pwd, then write 'hello world' to /work/temp.txt".
- Expected minimum:
  - 1 `exec` for `pwd`
  - 1 `exec` for the write command (`bash -lc ...`)
  - 1 `fs_create` for `/work/temp.txt`
- Additional `exec` rows for `codex` are expected.
- `job_id` should be populated for these rows.

Case C: interactive session (tui)
- Same prompt as Case B.
- Expected minimum: same as Case B.
- Additional `exec` rows may be higher because of PTY/session setup.
- `session_id` should be populated for these rows.

## Additional Filter Scenarios (recommended)

- Helper suppression:
  - `locale-check`, `getconf`, `uname`, and `git rev-parse` do not appear.
- Path filtering:
  - writes outside `/work` are excluded.
- Rename/unlink/metadata:
  - `mv` yields `fs_rename`
  - `rm` yields `fs_unlink`
  - `chmod` yields `fs_meta`
- Session/job mapping:
  - Interactive sessions map to `logs/sessions/*/meta.json`.
  - Server jobs map to `logs/jobs/*/input.json` + `status.json`.

## eBPF Filter Test Cases (proposed)

These validate the eBPF filter behavior and ownership attribution using raw
audit exec events as the PID tree source.

Minimums (unit + integration):
- Keeps only events whose PID is in the agent-owned PID tree.
- Uses session/job time-window mapping (sessions take precedence).
- Preserves DNS query/response as separate events.
- Honors exclusion lists (comm, unix paths, dst IP/port).
- Optionally attaches `cmd` from the last exec for the same PID.

Suggested cases:
- Owned PID inclusion + `cmd` linking.
- Unowned PID exclusion.
- Exclude `unix_connect` to `/var/run/nscd/socket` and `/var/run/docker.raw.sock`.
- Exclude comms like `initd`, `dockerd`, `chown`.
- Preserve `dns_query` and `dns_response`.
- Job/session precedence (session wins, job_id omitted when session_id present).

## Unified Merge Test Cases (proposed)

These validate the merger that produces a single UI timeline.

Suggested cases:
- Merge audit + eBPF streams into a single JSONL output.
- Deterministic ordering by timestamp, then source, then PID.
- Preserve session_id/job_id from inputs.
- Normalize into a common schema with `details` for source-specific fields.
- Handles empty inputs gracefully.

## Integration Scripts

- Stub: `scripts/run_integration_stub.sh`
- Codex: `scripts/run_integration_codex.sh`
- Filter (no harness): `scripts/run_integration_filter_no_harness.sh`
- Filter (job/server): `scripts/run_integration_filter_job.sh`
- Filter (tui): `scripts/run_integration_filter_tui.sh`
- Filter (eBPF, job/server): `scripts/run_integration_filter_ebpf_job.sh` (requires eBPF filter)
- Merge (audit + eBPF): `scripts/run_integration_merge.sh` (requires unified merger)

The filter scripts run direct shell commands (no Codex dependency) so file
events are deterministic. The TUI variant requires the `script` command to
allocate a pseudo-TTY.

## Unit Tests

Unit tests live in `collector/tests/` and can be run with:
```bash
python3 -m unittest discover -s collector/tests
```

Harness unit tests live in `harness/tests/` and can be run with:
```bash
python3 -m unittest discover -s harness/tests
```

Suggested fixture coverage:
- Grouping by `msg=audit(...:<seq>)`.
- Exec argv parsing, shell `-lc` extraction.
- Helper suppression by comm/argv prefix.
- FS event typing from PATH nametypes.
- Path prefix filtering for `/work`.
- Session/job time-window mapping.
- eBPF event inclusion/exclusion.
- Unified merge ordering + schema normalization.
