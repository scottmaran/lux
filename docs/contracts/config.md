# Lasso `config.yaml` Reference
Layer: Contract

`config.yaml` is the canonical runtime contract for `lasso`.

For most users, the recommended way to create/update this file is the setup
wizard:

```bash
lasso setup
```

## Default Location

- `~/.config/lasso/config.yaml`

Overrides:
- `lasso --config <path>`
- `LASSO_CONFIG`
- `LASSO_CONFIG_DIR` (directory containing `config.yaml` and `compose.env`)

## Schema (v2)

```yaml
version: 2

paths:
  log_root: ~/lasso-logs
  workspace_root: ~/lasso-workspace

release:
  tag: ""

docker:
  project_name: lasso

harness:
  api_host: 127.0.0.1
  api_port: 8081
  api_token: ""

collector:
  auto_start: true
  idle_timeout_min: 10080
  rotate_every_min: 1440

runtime_control_plane:
  # empty means "<config_dir>/runtime/control_plane.sock"
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
        secrets_file: ~/.config/lasso/secrets/codex.env
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
        secrets_file: ~/.config/lasso/secrets/claude.env
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

## Migration From v1

`version: 1` configs are not supported by the current CLI.

To migrate:
1. Update `version: 1` -> `version: 2`.
2. Add a `providers:` block (copy from the default config and then customize).
3. Run:
   - `lasso config validate`
   - `lasso config apply`

## Required Concepts

- `version` must be `2`.
- `collector` is optional and defaults to:
  - `auto_start: true`
  - `idle_timeout_min: 10080`
  - `rotate_every_min: 1440`
- `runtime_control_plane` is optional and defaults to:
  - `socket_path: <config_dir>/runtime/control_plane.sock`
  - `socket_gid: <invoking_user_primary_gid>`
- `providers.<name>.auth_mode` must be explicit:
  - `api_key`
  - `host_state`
- `providers.<name>.mount_host_state_in_api_mode` defaults `false`.

## API-Key Secrets Files

Provider secrets files are only used when `auth_mode=api_key`.

The setup wizard can optionally create these secrets files for you.

Examples:

```bash
mkdir -p ~/.config/lasso/secrets
chmod 700 ~/.config/lasso/secrets

printf 'OPENAI_API_KEY=%s\n' 'YOUR_KEY' > ~/.config/lasso/secrets/codex.env
printf 'ANTHROPIC_API_KEY=%s\n' 'YOUR_KEY' > ~/.config/lasso/secrets/claude.env
chmod 600 ~/.config/lasso/secrets/codex.env ~/.config/lasso/secrets/claude.env
```

## Host-State Mode and macOS Claude Caveat

`auth_mode=host_state` mounts host auth files into the agent container and copies them into `/home/agent`.

For Claude on macOS, this is best-effort only:
- Claude auth can depend on macOS Keychain.
- Linux containers cannot access macOS Keychain.
- Even with `~/.claude*` mounts, auth may still fail in-container.

If this happens, switch the provider to `auth_mode=api_key`.

## What `lasso config apply` Does

- Validates config schema and provider blocks.
- Writes compose env file (default `~/.config/lasso/compose.env`).
- Ensures `paths.log_root` and `paths.workspace_root` exist.

Generated compose env values include:
- `LASSO_VERSION`
- `LASSO_LOG_ROOT`
- `LASSO_WORKSPACE_ROOT`
- `LASSO_RUNTIME_DIR`
- `LASSO_RUNTIME_GID`
- `HARNESS_HTTP_PORT`
- `HARNESS_API_TOKEN` (if configured)
- `COLLECTOR_ROOT_COMM` (merged from provider ownership config)
