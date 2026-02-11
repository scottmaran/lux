# Lasso CLI

The `lasso` CLI is the primary entry point for running the stack. It reads a
single config file, generates a compose env file, and shells out to `docker
compose` for lifecycle commands. For non‑interactive runs it calls the harness
HTTP API; for TUI runs it starts the harness in TUI mode.

## How it works (brief)

1) Read config (`~/.config/lasso/config.yaml`).
2) `config apply` generates `compose.env` with `LASSO_VERSION`,
   `LASSO_LOG_ROOT`, and `LASSO_WORKSPACE_ROOT`.
3) `up/down/status/tui` shell out to `docker compose` with the bundle’s compose
   files and the generated env file.
4) `run` and `jobs` call the harness HTTP API on `127.0.0.1:8081`.

## Examples

```bash
lasso config init
lasso config apply
lasso up --codex
lasso status
lasso tui --codex
lasso down --volumes --remove-orphans
lasso paths --json
lasso update check
lasso update apply --yes
lasso logs stats
```

## Commands

### config
Manage the canonical config file.

- `lasso config init`  
  Create the config file if missing.

- `lasso config edit`  
  Open config in `$VISUAL` or `$EDITOR`.

- `lasso config validate`  
  Validate config (errors on unknown fields).

- `lasso config apply`  
  Generate compose env file and create log/workspace dirs.

### up
Start the stack via Docker Compose.

Options:
- `--codex`: include `compose.codex.yml`.
- `--ui`: include `compose.ui.yml`.
- `--pull <always|missing|never>`: control image pulls.
- `--wait`: wait until services are running/healthy.
- `--timeout-sec <n>`: wait timeout in seconds (requires `--wait`).

### down
Stop the stack via Docker Compose.

Options:
- `--codex`: include `compose.codex.yml`.
- `--ui`: include `compose.ui.yml`.
- `--volumes`: remove named volumes.
- `--remove-orphans`: remove orphaned containers.

### status
Show running containers (compose `ps` output).

Options:
- `--codex`: include `compose.codex.yml`.
- `--ui`: include `compose.ui.yml`.

### run
Trigger a non‑interactive run via the harness HTTP API.

Usage:
- `lasso run "prompt text"`

Options:
- `--capture-input <bool>`: store prompt in logs (default true).
- `--cwd <path>`: working directory inside the agent.
- `--timeout-sec <seconds>`: job timeout.
- `--env KEY=VALUE` (repeatable): extra env vars for the run.

### tui
Run an interactive session (PTY) via the harness.

Options:
- `--codex`: include `compose.codex.yml`.

### jobs
Inspect job records written by the harness.

- `lasso jobs list`  
  List job IDs under the log root.

- `lasso jobs get <id>`  
  Show job status.json for a specific job.

### doctor
Check local prerequisites (Docker available, log root writable).

### paths
Print resolved runtime paths (`config`, `compose.env`, bundle, log/work roots,
install/bin layout). Useful for automation and tests.

### uninstall
Remove the CLI install footprint with explicit safety controls.

Default behavior:
- Remove CLI symlink/current install only.
- Keep config and data unless flags are provided.
- Requires `--yes` unless using `--dry-run`.

Options:
- `--remove-config`: remove `config.yaml` and `compose.env`.
- `--remove-data`: remove resolved log/workspace roots.
- `--all-versions`: remove all installed versions under install dir.
- `--yes`: confirm destructive actions.
- `--dry-run`: preview removals without mutating filesystem.
- `--force`: skip the pre-uninstall `down` attempt.

### update
Manage release updates for the installed CLI bundle.

- `lasso update check`
  - Resolves latest release and reports whether the current install is up to date.

- `lasso update apply [--to <version>] [--latest] [--yes] [--dry-run]`
  - Downloads release bundle + checksum, verifies SHA256, and atomically switches
    `current` + binary symlinks.
  - Defaults to latest release when `--to` is omitted.
  - Requires `--yes` unless using `--dry-run`.

- `lasso update rollback [--previous|--to <version>] [--yes] [--dry-run]`
  - Switches back to an already installed version without re-downloading.
  - `--previous` (or no target) chooses the prior installed version.
  - Requires `--yes` unless using `--dry-run`.

### logs
Inspect logs at a high level.

- `lasso logs stats`  
  Estimate average MB/hour from recent sessions.

- `lasso logs tail [--lines N] [--file <name>]`  
  Tail common logs (`audit`, `ebpf`, `timeline`) or a specific file path
  relative to the log root.

## Global Options

- `--config <path>`: Use a specific config file.
- `--json`: Emit machine‑readable JSON output.
- `--compose-file <path>`: Override compose files (repeatable).
- `--bundle-dir <path>`: Override bundle directory (advanced; for dev use).
- `--env-file <path>`: Override compose env file path (advanced; for dev use).

## Configuration

Default config path: `~/.config/lasso/config.yaml`  
Override with: `--config <path>` or `LASSO_CONFIG`.

`lasso config apply` writes a compose env file (default
`~/.config/lasso/compose.env`) and creates the log/workspace directories defined
in the config.
For `lasso run`, `harness.api_token` must be set in the config (or provided via
`HARNESS_API_TOKEN` in the compose env file).
