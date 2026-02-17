# Spec: Home-Scoped Workspace And External Log Root Defaults

Status: draft
Owner: codex
Created: 2026-02-17
Last updated: 2026-02-17

## Problem
Current workspace/log root defaults make it easy to accidentally expose the evidence sink
via a workspace mount. The default UX is also ambiguous about what the agent can access,
leading to user confusion and potential invariant violations.

## Goals
- Default the agent workspace to the user home directory.
- Default the log root outside the user home directory with OS-specific paths.
- Enforce that workspace paths are under $HOME and log roots are outside $HOME.
- Keep evidence accessible to the agent read-only at `/logs`.
- Provide a simple, consistent CLI path model for workspace and start directory.
- Keep all config creation entry points aligned on defaults (not just setup/config init).
- Keep collector and provider planes on a single effective workspace for a run.

## Non-Goals
- Supporting workspaces outside $HOME.
- Mounting the full host filesystem into the agent container.
- Changing evidence schemas or run layout.
- Supporting non-macOS/non-Linux host defaults.

## User Experience
- `lasso setup`, `lasso config init`, and other config-bootstrap paths produce OS-specific defaults:
  - macOS log root: `/Users/Shared/Lasso/logs`
  - Linux log root: `/var/lib/lasso/logs`
  - workspace: `$HOME`
- Unsupported host OS fails fast with an actionable error (macOS/Linux only).
- New/updated CLI flags:
  - `lasso up --collector-only [--workspace <host-path>]`
  - `lasso up --provider <name> [--workspace <host-path>]`
  - `lasso run --provider <name> [--start-dir <host-path>] <prompt>`
  - `lasso tui --provider <name> [--start-dir <host-path>]`
- `lasso run --cwd` is removed and replaced by `--start-dir`.
- If `--start-dir` is omitted, default is the host current working directory.
- Hard errors for invalid paths with actionable messages.
- Agent mount surface remains minimal and explicit:
  - baseline runtime mounts (`/work`, `/logs` read-only, `/config` read-only), plus
  - provider auth/state mounts (read-only) when configured.

## Design
- Default-path helper:
  - Add a shared helper that computes defaults for `paths.log_root` and `paths.workspace_root`
    from `(os, home)`.
  - Supported host OS values:
    - macOS: `log_root=/Users/Shared/Lasso/logs`, `workspace_root=$HOME`
    - Linux: `log_root=/var/lib/lasso/logs`, `workspace_root=$HOME`
    - other: hard error (unsupported host OS for defaults)
  - This helper becomes the source of truth for defaults and is used by:
    - `lasso config init`
    - `lasso setup` when config is missing
    - `lasso config edit` when config is missing
    - runtime defaults used by `Config::default()` / `Paths::default()`
    - installer bootstrap path (config creation)
- Path canonicalization and validation:
  - Add shared policy-path resolver for config and CLI overrides:
    - expands `~`
    - requires absolute host paths
    - canonicalizes existing prefixes and resolves lexical suffixes
    - rejects invalid/missing `HOME`
  - Config validation rules:
    - `workspace_root` must be equal to or under `$HOME` (canonical descendant check)
    - `log_root` must be outside `$HOME` (canonical containment check)
    - `workspace_root` and `log_root` must not overlap in either direction
- Run-scoped effective workspace:
  - Effective workspace for a run is chosen when collector plane starts:
    - `--workspace` on `up --collector-only` if provided
    - otherwise config `paths.workspace_root`
  - Persist effective workspace in active run state.
  - `up --provider` must use the same effective workspace:
    - if `--workspace` is provided and differs from active run workspace: hard error
  - Compose env overrides include run-scoped workspace so collector/provider use the same mount.
- Start directory semantics:
  - `--start-dir` is a host path.
  - If omitted: host CWD.
  - Validation:
    - canonical start-dir must be inside effective workspace
  - Mapping:
    - convert host start-dir to container path under `/work` using path relative to workspace root
  - `run` sends mapped value as harness `cwd`.
  - `tui` passes mapped value through `HARNESS_AGENT_WORKDIR` for the TUI invocation.
- Harness API hard-error behavior:
  - Replace invalid-cwd silent fallback with request rejection.
  - Invalid `cwd` in `/run` returns HTTP 400 with an explicit error.
  - CLI path validation remains in front as first layer; harness enforces same contract defensively.
- Log root creation:
  - If missing, create during `apply_config`.
  - If creation fails, error with instructions (Linux likely requires a one-time
    `sudo mkdir -p /var/lib/lasso/logs` + `sudo chown -R $USER /var/lib/lasso/logs`).
- Runtime mount wiring:
  - Workspace mount targets the run-effective workspace.
  - `/logs` remains read-only in agent and writable only in trusted components as today.
  - Existing required mounts (`/config`) and provider auth/state read-only mounts remain.
- Precedence:
  - `up --collector-only --workspace` overrides config for that run.
  - `up --provider --workspace` may be omitted or must equal run-effective workspace.
  - `run/tui --start-dir` overrides default host CWD for that invocation.

## Data / Schema Changes
- None. No changes to evidence schemas or run layout.
- Active run state metadata is extended to include effective workspace path.

## Security / Trust Model
- Reinforces Invariant 2 by keeping the log root outside the agent workspace.
- Agent retains read-only access to evidence at `/logs`; no write access is granted.
- The `/logs` read-only mount is unchanged from current behavior.
- Run-consistent workspace selection avoids collector/provider observation-boundary drift.

## Failure Modes
- Unsupported OS for default computation: hard error describing supported OS list.
- Missing/unusable `$HOME`: hard error explaining requirement.
- Relative or non-canonicalizable path input: hard error with correction guidance.
- Workspace outside `$HOME`: hard error with a message explaining the restriction.
- Log root inside `$HOME`: hard error with a message explaining evidence safety.
- Workspace/log root overlap in either direction: hard error.
- `--start-dir` outside workspace: hard error (including when defaulting to host CWD).
- `up --provider --workspace` mismatch with active run workspace: hard error.
- Harness `/run` request with invalid `cwd`: HTTP 400 (no silent fallback).
- Log root creation fails: hard error with platform-specific remediation steps.

## Acceptance Criteria
- All config bootstrap paths use the same OS-specific defaults for log root/workspace.
- Config validation rejects a workspace outside `$HOME`.
- Config validation rejects a log root inside `$HOME`.
- Config validation rejects workspace/log_root overlap in either direction.
- `--workspace` and `--start-dir` behavior matches command scope and precedence above.
- Collector/provider startup for a run uses one consistent effective workspace.
- `lasso run --cwd` is removed; `--start-dir` is the supported flag.
- Invalid start-dir/cwd is a hard error in both CLI and harness API surfaces.
- Agent container mount contract remains secure:
  - `/logs` read-only in agent,
  - required control/auth mounts preserved,
  - no full-host mount expansion.
- All tests in the test suite pass.

## Test Plan
- Rust unit tests (`lasso`):
  - default-path helper behavior (macOS/Linux/unsupported OS)
  - path canonicalization and validation (workspace under home, log root outside home,
    overlap rejection, missing HOME, relative path rejection, symlink-escape edge cases)
  - run-effective workspace persistence and mismatch checks
- CLI tests (`lasso/tests/cli.rs`):
  - config bootstrap defaults under controlled HOME
  - `--workspace` / `--start-dir` parsing and precedence
  - `--cwd` removal behavior
  - actionable errors for out-of-policy paths
- Integration tests:
  - mount contract parity (`/work`, `/logs`, `/config`, provider auth mounts)
  - `run` + `tui` start-dir mapping from host path to `/work/...`
  - harness `/run` invalid cwd returns HTTP 400
- Test migration for home-scope policy:
  - update existing CLI/integration tests to run with isolated HOME roots
  - for valid cases, place workspace under HOME
  - for invalid-path tests, intentionally use outside-HOME paths and assert hard errors
- Regression tests:
  - prevent workspace/log_root overlap and evidence write access regressions
- Manual verification: optional spot-check in `lasso setup` for default paths.

## Rollout
- Behavior-changing defaults and CLI surface:
  - `run --cwd` removed in favor of `--start-dir`
  - harness invalid-cwd behavior changes from fallback to hard-error
- No migration note required (stealth), but docs/contracts/tests must be updated atomically.
- Update docs to reflect new defaults and constraints.

## Open Questions
- None.
