# Lasso CLI Integration Tests

These scripts validate the Lasso CLI end-to-end using the CLI (not raw docker
commands). They create temporary log/workspace directories, generate a
config, and drive `lasso` commands to validate artifacts.

## Prerequisites

- `lasso` CLI available in `PATH` (or set `LASSO_BIN` to the binary path).
- Docker running locally.
- GHCR auth for private images (run `docker login ghcr.io`).
- Python 3 available in `PATH` (used for JSON parsing in scripts).
- `script` command + interactive TTY for TUI PTY tests (required).

## Environment Variables

- `LASSO_BIN` — path to the CLI binary (default: `lasso`).
- `LASSO_VERSION` — image tag to use (default: `v0.1.0`).
- `HARNESS_API_TOKEN` — harness API token used by `lasso run` (default: `dev-token`).
- `LASSO_BUNDLE_DIR` — directory containing compose files (default: repo root).
- `LASSO_PROJECT_NAME` — explicit compose project name (default: per-script temp-derived name).

If running from source, point `LASSO_BIN` at the built binary, e.g.:
`LASSO_BIN=~/lasso/lasso/target/debug/lasso`.

Each script creates a temporary config, log root, and workspace root under a
fresh temp directory. No permanent files are written to your home directory.
GHCR auth is handled by Docker’s credential store (no extra env vars needed).
Each lifecycle script uses unconditional teardown (`trap ... EXIT`) so cleanup
runs on both success and failure.

## Run All Tests

Step-by-step:
1) Ensure the CLI is available:
   - `lasso --help`
   - Or set `LASSO_BIN=/path/to/lasso`
2) Ensure Docker is running.
3) Authenticate to GHCR (required for private images):
   - `docker login ghcr.io`
4) Run the full suite:

```bash
scripts/cli_scripts/run_all.sh
```

## Scripts Summary

- `00_config_init.sh`
  - Validates `lasso config init` creates a config when missing and preserves
    an existing config.

- `01_config_validate_unknown.sh`
  - Ensures unknown config fields cause validation errors.

- `02_config_apply.sh`
  - Validates `lasso config apply` writes the compose env file and creates
    log/workspace roots.

- `03_config_apply_invalid.sh`
  - Ensures invalid configs produce a clear, actionable error message.

- `04_doctor_no_docker.sh`
  - Ensures `lasso doctor --json` reports docker missing when `PATH` is empty.

- `05_doctor_log_root_unwritable.sh`
  - Ensures `lasso doctor --json` reports unwritable log root.

- `06_status_no_docker.sh`
  - Ensures `lasso status --collector-only` fails cleanly when docker is unavailable.

- `10_stack_smoke.sh`
  - Full stack smoke test:
    `up --collector-only` → `up --provider codex` → `status --provider codex` →
    raw logs present → `run --provider codex` artifacts → second `run` has distinct
    job id → `tui --provider codex` session artifacts (requires interactive TTY + `script`) →
    `down --provider codex` + `down --collector-only` → status is empty.

- `11_upgrade_env.sh`
  - Ensures `lasso config apply` rewrites the compose env file when the
    release tag changes (simulates upgrade).

- `12_missing_ghcr_auth.sh`
  - Validates that `lasso up` fails with an auth-related error when GHCR
    credentials are missing (skips if already logged in).
    It starts `up --collector-only` first and then attempts `up --provider codex`.

- `13_up_wait_timeout.sh`
  - Validates `lasso up --collector-only --wait --timeout-sec` reaches running state and
    `lasso down --collector-only` stops the collector plane.

- `14_down_cleanup_flags.sh`
  - Validates provider-plane down behavior:
    `up --collector-only` + `up --provider codex` creates the project volume,
    `down --provider codex` stops agent/harness without removing volumes,
    then `down --collector-only` stops the collector.

- `15_paths_json.sh`
  - Validates `lasso paths --json` returns resolved config/env/install/runtime
    paths with override support.

- `16_uninstall_dry_run.sh`
  - Validates `lasso uninstall --dry-run` reports planned removals without
    mutating install/config/data paths.

- `17_uninstall_exec.sh`
  - Validates `lasso uninstall --yes` removes requested targets and stops the
  running compose stack before deletion.

- `18_update_dry_run.sh`
  - Validates `lasso update apply --dry-run --to <version>` resolves and reports
    target paths/version without mutating install symlinks.

- `19_update_rollback_dry_run.sh`
  - Validates `lasso update rollback --dry-run --previous` selects the correct
    prior installed version without mutating current links.
