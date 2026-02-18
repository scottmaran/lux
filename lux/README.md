# Lux CLI (Rust)

This directory contains the Rust source for the `lux` CLI.

## What it does

- Reads the canonical config (`~/.config/lux/config.yaml`).
- Writes a compose env file (`~/.config/lux/compose.env`).
- Runs a local runtime control-plane daemon over Unix socket.
- Wraps `docker compose` for stack lifecycle commands.
- Calls the harness HTTP API for non‑interactive runs.
- Creates a run id on `up` and scopes logs under `<log_root>/lux__.../`.

## Build

```bash
cd lux
cargo build
```

## Run locally (from repo root)

When running from source, point `LUX_BUNDLE_DIR` to the repo root so the CLI
can find `compose.yml` and related files.

```bash
cd lux
cargo build
export LUX_BUNDLE_DIR=$(cd .. && pwd)
./target/debug/lux config init
./target/debug/lux config apply
./target/debug/lux runtime up
./target/debug/lux ui up
./target/debug/lux shim install codex
./target/debug/lux run --provider codex --start-dir "$PWD" "hello"
```

## Tests

```bash
cd lux
cargo test
```

## Notes

- `--config <path>` overrides the default config path.
- `--json` enables machine‑readable output.
- `run --cwd` is removed; use `run --start-dir <host-path>`.
