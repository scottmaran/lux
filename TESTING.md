# Testing Guide

This document describes how to validate the audit pipeline and the planned
audit filter behavior.

## Test Layers

- Collector smoke tests (raw auditd + eBPF logs).
- Integration tests for harness + agent workflows.
- Audit filter tests (spec-driven; filter script pending).
- Unit tests with fixture logs for deterministic parsing.

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

## Audit Filter Test Cases (spec)

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

Case C: interactive session (tui)
- Same prompt as Case B.
- Expected minimum: same as Case B.
- Additional `exec` rows may be higher because of PTY/session setup.

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

## Integration Scripts

- Stub: `scripts/run_integration_stub.sh`
- Codex: `scripts/run_integration_codex.sh`

These validate the harness stack end-to-end. They should be extended with a
prompt that writes to `/work` to verify `fs_*` outputs in the filter.

## Unit Tests (planned)

Recommended location and structure:
- Fixtures: `collector/testdata/` (small audit.log excerpts)
- Tests: `collector/tests/` (pytest)

Suggested fixture coverage:
- Grouping by `msg=audit(...:<seq>)`.
- Exec argv parsing, shell `-lc` extraction.
- Helper suppression by comm/argv prefix.
- FS event typing from PATH nametypes.
- Path prefix filtering for `/work`.
- Session/job time-window mapping.

