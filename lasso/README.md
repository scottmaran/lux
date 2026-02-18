# Lasso CLI (Rust)

This directory contains the Rust source for the `lasso` CLI.

## What it does

- Reads the canonical config (`~/.config/lasso/config.yaml`).
- Writes a compose env file (`~/.config/lasso/compose.env`).
- Wraps `docker compose` for stack lifecycle commands.
- Calls the harness HTTP API for non‑interactive runs.
- Creates a run id on `up` and scopes logs under `<log_root>/lasso__.../`.

## Build

```bash
cd lasso
cargo build
```

## Run locally (from repo root)

When running from source, point `LASSO_BUNDLE_DIR` to the repo root so the CLI
can find `compose.yml` and related files.

```bash
cd lasso
cargo build
export LASSO_BUNDLE_DIR=$(cd .. && pwd)
./target/debug/lasso config init
./target/debug/lasso config apply
./target/debug/lasso up --collector-only
./target/debug/lasso up --provider codex
./target/debug/lasso run --provider codex --start-dir "$PWD" "hello"
```

## Tests

```bash
cd lasso
cargo test
```

## Notes

- `--config <path>` overrides the default config path.
- `--json` enables machine‑readable output.
- `run --cwd` is removed; use `run --start-dir <host-path>`.
