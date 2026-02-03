# Lasso CLI Integration Tests

These scripts validate the Lasso CLI end-to-end using the CLI (not raw docker
commands). They create temporary log/workspace directories, generate a
config, and drive `lasso` commands to validate artifacts.

## Prerequisites

- `lasso` CLI available in `PATH` (or set `LASSO_BIN` to the binary path).
- Docker running locally.
- GHCR auth for private images (run `docker login ghcr.io`).
- Python 3 available in `PATH` (used for JSON parsing in scripts).
- Optional: `script` command for TUI PTY tests (skips if missing).

## Environment Variables

- `LASSO_BIN` — path to the CLI binary (default: `lasso`).
- `LASSO_VERSION` — image tag to use (default: `v0.1.0`).
- `HARNESS_API_TOKEN` — harness API token used by `lasso run` (default: `dev-token`).
- `LASSO_BUNDLE_DIR` — directory containing compose files (default: repo root).

Each script creates a temporary config, log root, and workspace root under a
fresh temp directory. No permanent files are written to your home directory.
GHCR auth is handled by Docker’s credential store (no extra env vars needed).

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
  - Ensures `lasso status` fails cleanly when docker is unavailable.

- `10_stack_smoke.sh`
  - Full stack smoke test: `up` → `status` → raw logs present → `run` job
    artifacts → second `run` has distinct job id → `tui` session artifacts
    (if `script` exists) → `down` → status is empty.

- `11_upgrade_env.sh`
  - Ensures `lasso config apply` rewrites the compose env file when the
    release tag changes (simulates upgrade).

- `12_missing_ghcr_auth.sh`
  - Validates that `lasso up` fails with an auth-related error when GHCR
    credentials are missing (skips if already logged in).
