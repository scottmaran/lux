# Lux `config.yaml` Reference
Layer: Contract

`config.yaml` is the canonical runtime contract for `lux`.

For most users, create/update it with:

```bash
lux setup
```

## Default Location

- `~/.config/lux/config.yaml`

Overrides:
- `lux --config <path>`
- `LUX_CONFIG`
- `LUX_CONFIG_DIR` (directory containing `config.yaml`)

## Schema (v2)

```yaml
version: 2

paths:
  # macOS default: /Users/Shared/Lux
  # Linux default: /var/lib/lux
  trusted_root: /var/lib/lux
  # default: <trusted_root>/logs
  log_root: /var/lib/lux/logs
  # default: $HOME
  workspace_root: /home/alice

shims:
  # default: <trusted_root>/bin
  bin_dir: /var/lib/lux/bin

release:
  tag: ""

docker:
  project_name: lux

harness:
  api_host: 127.0.0.1
  api_port: 8081
  api_token: ""

collector:
  auto_start: true
  idle_timeout_min: 10080
  rotate_every_min: 1440

runtime_control_plane:
  # empty means "<trusted_root>/runtime/control_plane.sock"
  # (with automatic short-path fallback when Unix socket limits require it)
  socket_path: ""
  # optional; defaults to invoking user's primary gid
  socket_gid: null

providers:
  codex:
    auth_mode: api_key
    mount_host_state_in_api_mode: false
    commands:
      tui: "codex -C /work -s danger-full-access"
      run_template: "codex -C /work -s danger-full-access exec {prompt}"
    auth:
      api_key:
        secrets_file: /var/lib/lux/secrets/codex.env
        env_key: OPENAI_API_KEY
      host_state:
        paths:
          - ~/.codex/auth.json
          - ~/.codex/skills
    ownership:
      root_comm:
        - bash
        - sh
        - setsid
        - timeout
        - codex

  claude:
    auth_mode: host_state
    mount_host_state_in_api_mode: false
    commands:
      tui: "claude"
      run_template: "claude -p {prompt}"
    auth:
      api_key:
        secrets_file: /var/lib/lux/secrets/claude.env
        env_key: ANTHROPIC_API_KEY
      host_state:
        paths:
          - ~/.claude.json
          - ~/.claude
          - ~/.config/claude-code/auth.json
    ownership:
      root_comm:
        - bash
        - sh
        - setsid
        - timeout
        - claude
```

## Required Concepts

- `version` must be `2`.
- `paths.trusted_root` must be explicitly present in config.
- `collector` defaults:
  - `auto_start: true`
  - `idle_timeout_min: 10080`
  - `rotate_every_min: 1440`
- `runtime_control_plane` defaults:
  - `socket_path: <trusted_root>/runtime/control_plane.sock`
  - `socket_gid: <invoking_user_primary_gid>`
- `providers.<name>.auth_mode` must be explicit:
  - `api_key`
  - `host_state`
- `providers.<name>.mount_host_state_in_api_mode` defaults `false`.

## Path Policy

`paths.*` and `shims.bin_dir` are validated as a trust boundary:

- Host OS must be `macos` or `linux`.
- `$HOME` must resolve to an existing absolute directory.
- `workspace_root` must be equal to or under `$HOME`.
- `trusted_root` must be outside `$HOME`.
- `log_root` must be inside `trusted_root`.
- `shims.bin_dir` must be inside `trusted_root`.
- `workspace_root` and `log_root` must not overlap.
- `workspace_root` and `shims.bin_dir` must not overlap.

Default path computation used by `setup`, `config init`, and installer bootstrap:

- macOS:
  - `paths.trusted_root=/Users/Shared/Lux`
  - `paths.log_root=/Users/Shared/Lux/logs`
  - `shims.bin_dir=/Users/Shared/Lux/bin`
  - `paths.workspace_root=$HOME`
- Linux:
  - `paths.trusted_root=/var/lib/lux`
  - `paths.log_root=/var/lib/lux/logs`
  - `shims.bin_dir=/var/lib/lux/bin`
  - `paths.workspace_root=$HOME`

## API-Key Secrets Files

Provider secrets files are only used when `auth_mode=api_key`.

Default locations:

- `<trusted_root>/secrets/codex.env`
- `<trusted_root>/secrets/claude.env`

Example:

```bash
mkdir -p /var/lib/lux/secrets
chmod 700 /var/lib/lux/secrets
printf 'OPENAI_API_KEY=%s\n' 'YOUR_KEY' > /var/lib/lux/secrets/codex.env
printf 'ANTHROPIC_API_KEY=%s\n' 'YOUR_KEY' > /var/lib/lux/secrets/claude.env
chmod 600 /var/lib/lux/secrets/codex.env /var/lib/lux/secrets/claude.env
```

## Host-State Mode and macOS Claude Caveat

`auth_mode=host_state` mounts host auth files into the agent container and copies them into `/home/agent`.

For Claude on macOS, this is best-effort only:
- Claude auth can depend on macOS Keychain.
- Linux containers cannot access macOS Keychain.
- Even with `~/.claude*` mounts, auth may still fail in-container.

If this happens, switch the provider to `auth_mode=api_key`.

## What `lux config apply` Does

- Validates config schema and provider blocks.
- Enforces trust/path policy.
- Writes compose env file (default `<trusted_root>/state/compose.env`).
- Ensures these directories exist:
  - `paths.trusted_root`
  - `paths.log_root`
  - `paths.workspace_root`
  - `<trusted_root>/runtime`
  - `<trusted_root>/state`
  - `<trusted_root>/secrets`
  - `shims.bin_dir`

Generated compose env values include:
- `LUX_VERSION`
- `LUX_TRUSTED_ROOT`
- `LUX_LOG_ROOT`
- `LUX_STATE_DIR`
- `LUX_SECRETS_DIR`
- `LUX_SHIMS_BIN_DIR`
- `LUX_WORKSPACE_ROOT`
- `LUX_RUNTIME_DIR`
- `LUX_RUNTIME_GID`
- `HARNESS_HTTP_PORT`
- `HARNESS_API_TOKEN` (if configured)
- `COLLECTOR_ROOT_COMM` (merged from provider ownership config)
