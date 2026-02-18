# Lasso CLI
Layer: Contract

`lasso` is the primary control plane for the stack. It validates config, writes compose env state, and orchestrates collector/provider lifecycle through `docker compose`.

## Lifecycle Model

- Collector plane: `collector` service only.
- Provider plane: `agent` + `harness` for one explicit provider.
- Provider is always explicit for agent-facing actions.

## Quick Start

```bash
lasso setup
lasso up --collector-only --wait
lasso up --provider codex --wait
lasso tui --provider codex
```

## Core Commands

### `setup`

Interactive setup wizard that updates `config.yaml` in place (preserving
comments/formatting) and optionally creates provider secrets files.

Path policy enforced by setup:
- `paths.workspace_root` must be under `$HOME`
- `paths.log_root` must be outside `$HOME`
- log/workspace paths must not overlap

Flags:
- `--defaults`: non-interactive mode (for scripts/CI)
- `--dry-run`: show planned changes without writing
- `--no-apply`: skip `lasso config apply`
- `--yes`: in interactive mode, skip the final confirmation prompt

### `config`

- `lasso config init`
- `lasso config edit`
- `lasso config validate`
- `lasso config apply`

### `up`

Start either collector plane or provider plane.

- Collector only:
  - `lasso up --collector-only [--workspace <host-path>] [--wait --timeout-sec N]`
- Provider plane:
  - `lasso up --provider codex|claude [--workspace <host-path>] [--wait --timeout-sec N]`

Rules:
- `--collector-only` conflicts with `--provider`.
- `up --provider X` requires an active collector run (`up --collector-only` first).
- Provider mismatch hard-fails (no implicit provider switching).
- `--workspace` must be under `$HOME`, must not overlap log root, and applies to the run started by `up --collector-only`.
- `up --provider --workspace` is optional, but when provided it must exactly match the active run workspace.

### `down`

Stop either collector plane or provider plane.

- `lasso down --collector-only`
- `lasso down --provider codex|claude`

### `status`

Show compose status for one plane.

- `lasso status --collector-only`
- `lasso status --provider codex|claude`

### `tui`

Run an interactive harness TUI session for the active provider plane.

- `lasso tui --provider codex|claude [--start-dir <host-path>]`

### `run`

Submit a non-interactive harness job.

- `lasso run --provider codex|claude "prompt"`
- Optional: `--capture-input <bool> --start-dir <host-path> --timeout-sec <n> --env KEY=VALUE`

Notes:
- `run` requires active provider plane state for the selected provider.
- `--env` values are persisted in job metadata by design.
- `--start-dir` defaults to the host current working directory and must be inside the run workspace.

### `jobs`

- `lasso jobs list [--run-id <id>|--latest]`
- `lasso jobs get <id> [--run-id <id>|--latest]`

### `logs`

- `lasso logs stats [--run-id <id>|--latest]`
- `lasso logs tail [--lines N] [--file <audit|ebpf|timeline|path>] [--run-id <id>|--latest]`

### `doctor`

Checks local prerequisites:
- Docker daemon availability (`checks.docker`)
- Docker Compose availability (`checks.docker_compose`)
- Writable log root (`checks.log_root_writable`)

### `paths`

Prints resolved runtime paths and compose file list.

### `update`

- `lasso update check`
- `lasso update apply [--to <version>|--latest] [--yes|--dry-run]`
- `lasso update rollback [--to <version>|--previous] [--yes|--dry-run]`

### `uninstall`

Remove the CLI install footprint with explicit safety controls.

`lasso uninstall [--remove-config] [--all-versions] [--yes|--dry-run] [--force]`

Notes:
- Requires `--yes` unless using `--dry-run`.
- `uninstall` never deletes your log/workspace roots. Remove those manually if desired.

Options:
- `--remove-config`: remove `config.yaml` and `compose.env`.
- `--all-versions`: remove all installed versions under install dir.
- `--yes`: confirm destructive actions.
- `--dry-run`: preview removals without mutating filesystem.
- `--force`: skip the best-effort pre-uninstall stack shutdown attempt.

## Global Flags

- `--config <path>`
- `--json`
- `--compose-file <path>` (repeatable)
- `--bundle-dir <path>` (advanced/dev)
- `--env-file <path>` (advanced/dev)

## JSON Error Envelope

When `--json` is enabled, failures keep the existing top-level fields:
- `ok: false`
- `result: null`
- `error: "<string>"`

Process/command failures may also include additive structured details:
- `error_details.error_code` (stable identifier)
- `error_details.hint` (actionable remediation when available)
- `error_details.command` (failed command context)
- `error_details.raw_stderr` (raw stderr excerpt when available)
