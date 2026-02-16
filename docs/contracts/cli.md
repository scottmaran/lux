# Lasso CLI
Layer: Contract

`lasso` is the primary local control surface for stack lifecycle, runtime health,
and evidence-safe provider execution.

## Lifecycle Model

- Runtime control-plane: local daemon over Unix socket (`lasso runtime ...`).
- Collector plane: `collector` service only.
- Provider plane: `agent` + `harness` for one explicit provider.
- UI plane: `ui` service only (managed independently from collector/provider).

## Quick Start

```bash
lasso setup
lasso shim install codex claude
codex
```

Equivalent explicit lifecycle flow:

```bash
lasso up --collector-only --wait
lasso up --provider codex --wait
lasso tui --provider codex
```

## Core Commands

### `setup`

Interactive setup wizard that updates `config.yaml` and can create provider
secrets files.

Flags:
- `--defaults`
- `--dry-run`
- `--no-apply`
- `--yes`

### `config`

- `lasso config init`
- `lasso config edit`
- `lasso config validate`
- `lasso config apply`

### `runtime`

- `lasso runtime up`
- `lasso runtime down`
- `lasso runtime status`

Runtime is auto-started by normal lifecycle commands when needed.

### `ui`

- `lasso ui up [--wait --timeout-sec N] [--pull always|never|missing]`
- `lasso ui down`
- `lasso ui status`
- `lasso ui url`

Deprecated `--ui` flags on `up/down/status` are removed.

### `up`

Start either collector plane or provider plane.

- `lasso up --collector-only [--wait --timeout-sec N] [--pull ...]`
- `lasso up --provider codex|claude [--wait --timeout-sec N] [--pull ...]`

Rules:
- `--collector-only` conflicts with `--provider`.
- Provider mismatch hard-fails (no implicit provider switching).
- If `collector.auto_start=true`, provider start auto-bootstraps collector/run
  when needed.

### `down`

- `lasso down --collector-only`
- `lasso down --provider codex|claude`

### `status`

- `lasso status --collector-only`
- `lasso status --provider codex|claude`

### `shim`

- `lasso shim install <provider...>`
- `lasso shim uninstall <provider...>`
- `lasso shim list`
- `lasso shim exec <provider> -- <argv...>`

Shim v1 behavior:
- Full argv passthrough is preserved.
- Invocation must happen from within configured `paths.workspace_root`.
- Absolute host-path args are rejected with actionable error.

### `tui`

- `lasso tui --provider codex|claude`

### `run`

- `lasso run --provider codex|claude "prompt"`
- Optional: `--capture-input <bool> --cwd <path> --timeout-sec <n> --env KEY=VALUE`

### `jobs`

- `lasso jobs list [--run-id <id>|--latest]`
- `lasso jobs get <id> [--run-id <id>|--latest]`

### `logs`

- `lasso logs stats [--run-id <id>|--latest]`
- `lasso logs tail [--lines N] [--file <audit|ebpf|timeline|path>] [--run-id <id>|--latest]`

### `doctor`

Readiness checks for:
- docker/compose/runtime prerequisites
- log sink path permissions
- collector sensor prerequisites
- harness token/API sanity
- config/path coherence
- attribution prerequisites
- contract/schema compatibility checks

Flags:
- `--strict` fails on strict warning set in addition to errors.

### `paths`

Prints resolved runtime/config/install/compose paths.

### `update`

- `lasso update check`
- `lasso update apply [--to <version>|--latest] [--yes|--dry-run]`
- `lasso update rollback [--to <version>|--previous] [--yes|--dry-run]`

### `uninstall`

`lasso uninstall [--remove-config] [--all-versions] [--yes|--dry-run] [--force]`

## Global Flags

- `--config <path>`
- `--json`
- `--compose-file <path>` (repeatable)
- `--bundle-dir <path>` (advanced/dev)
- `--env-file <path>` (advanced/dev)
