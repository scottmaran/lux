# Lux CLI
Layer: Contract

`lux` is the primary local control surface for lifecycle, runtime health, and
provider execution.

## Lifecycle Model

- Runtime control plane: local daemon over Unix socket (`lux runtime ...`).
- Collector plane: `collector` service only.
- Provider plane: `agent` + `harness` for one explicit provider.
- UI plane: `ui` service only.

## Quick Start

```bash
lux setup
lux shim enable
codex
```

Equivalent explicit flow:

```bash
lux up --collector-only --wait
lux up --provider codex --wait
lux tui --provider codex
```

## Core Commands

### `setup`

Interactive setup wizard that updates `config.yaml` and can create provider
secrets files.

Path policy enforced by setup:
- `paths.trusted_root` must be outside `$HOME`.
- `paths.log_root` must be inside `paths.trusted_root`.
- `shims.bin_dir` must be inside `paths.trusted_root`.
- `paths.workspace_root` must be under `$HOME`.
- `paths.workspace_root` must not overlap `paths.log_root` or `shims.bin_dir`.

Flags:
- `--defaults`
- `--dry-run`
- `--no-apply`
- `--yes`

### `config`

- `lux config init`
- `lux config edit`
- `lux config validate`
- `lux config apply`

### `runtime`

- `lux runtime up`
- `lux runtime down`
- `lux runtime status`

Runtime is auto-started by normal lifecycle commands when needed.

### `ui`

- `lux ui up [--wait --timeout-sec N] [--pull always|never|missing]`
- `lux ui down`
- `lux ui status`
- `lux ui url`

Deprecated `--ui` flags on `up/down/status` are removed.

### `up`

Start either collector plane or provider plane.

- Collector only:
  - `lux up --collector-only [--workspace <host-path>] [--wait --timeout-sec N] [--pull ...]`
- Provider plane:
  - `lux up --provider <name> [--workspace <host-path>] [--wait --timeout-sec N] [--pull ...]`

Rules:
- `--collector-only` conflicts with `--provider`.
- Provider mismatch hard-fails (no implicit provider switching).
- `--workspace` must be under `$HOME`, must not overlap log root, and applies to
  the run started by `up --collector-only`.
- `up --provider --workspace` is optional, but when provided it must exactly
  match the active run workspace.
- If `collector.auto_start=true`, provider start auto-bootstraps collector/run
  when needed.

### `down`

- `lux down --collector-only`
- `lux down --provider <name>`

### `status`

- `lux status --collector-only`
- `lux status --provider <name>`

### `shim`

- `lux shim enable [provider...]`
- `lux shim disable [provider...]`
- `lux shim status [provider...]`
- `lux shim exec <provider> -- <argv...>`

Shim contract:
- `enable|disable|status` with no provider args target all providers in `config.providers`.
- `enable` is preflighted and atomic for shim writes (rollback on partial shim-write failure).
- `enable` and `disable` mutate only existing zsh/bash startup files via Lux-managed marker blocks.
- `status` reports summary state (`enabled|disabled|degraded`), per-provider readiness, and PATH persistence (`configured|partial|absent|no_startup_files`).
- `enable`/`disable` use two phases: shim mutation first, then shell PATH file mutation.
  - If shim mutation fails, PATH file mutation is skipped.
  - If PATH file mutation fails, command exits non-zero with `ok=false`, `result=null`, and partial progress in `error_details.partial_outcome`.
- `enable`/`disable` success JSON includes:
  - `action`, `providers`
  - `shim.ok`, `shim.rows[]` (`provider`, `path`, `changed`)
  - `path.ok`, `path.state`, `path.files[]` (`path`, `existed`, `managed_block_present`, `changed`)
  - `warnings[]`, `errors[]`
- `status` JSON includes:
  - `action`, `providers`, top-level `state`
  - `shims[]` (`provider`, `path`, `installed`, `path_safe`, `path_precedence_ok`, `resolved_candidates`)
  - `path_persistence.state`, `path_persistence.files[]` (`path`, `existed`, `managed_block_present`)
- exec preserves argv passthrough and cwd semantics via container workdir
  mapping; absolute host paths are rejected.

### `tui`

- `lux tui --provider <name> [--start-dir <host-path>]`

### `run`

- `lux run --provider <name> "prompt"`
- Optional: `--capture-input <bool> --start-dir <host-path> --timeout-sec <n> --env KEY=VALUE`

Notes:
- `run` requires active provider plane state for the selected provider.
- `--env` values are persisted in job metadata by design.
- `--start-dir` defaults to host cwd and must be inside run workspace.

### `jobs`

- `lux jobs list [--run-id <id>|--latest]`
- `lux jobs get <id> [--run-id <id>|--latest]`

### `logs`

- `lux logs stats [--run-id <id>|--latest]`
- `lux logs tail [--lines N] [--file <audit|ebpf|timeline|path>] [--run-id <id>|--latest]`

### `doctor`

Readiness checks for:
- docker/compose/runtime prerequisites
- trust-root path permissions and path coherence
- shim bin trust policy and PATH precedence
- harness token/API sanity
- attribution prerequisites
- contract/schema compatibility checks

Flags:
- `--strict` fails on strict warning set in addition to errors.

### `paths`

Prints resolved runtime/config/install/compose paths.

### `update`

- `lux update check`
- `lux update apply [--to <version>|--latest] [--yes|--dry-run]`
- `lux update rollback [--to <version>|--previous] [--yes|--dry-run]`

### `uninstall`

`lux uninstall [--remove-config] [--all-versions] [--yes|--dry-run] [--force]`

## Global Flags

- `--config <path>`
- `--json`
- `--compose-file <path>` (repeatable)
- `--bundle-dir <path>` (advanced/dev)
- `--env-file <path>` (advanced/dev)

## JSON Error Envelope

When `--json` is enabled, failures keep top-level fields:
- `ok: false`
- `result: null`
- `error: "<string>"`

Process/command failures may also include structured details:
- `error_details.error_code`
- `error_details.hint`
- `error_details.command`
- `error_details.raw_stderr`
- `error_details.partial_outcome` (for partial progress details while preserving `result: null`)
