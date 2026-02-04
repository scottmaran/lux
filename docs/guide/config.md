# Lasso config.yaml reference

The `config.yaml` file is the single source of truth for the `lasso` CLI. It
controls where logs/workspace live, which container image tags to pull, and how
the CLI connects to the harness API.

## Location and overrides

Default path:
- `~/.config/lasso/config.yaml`

Overrides:
- `lasso --config <path>`
- `LASSO_CONFIG` (path to a specific config file)
- `LASSO_CONFIG_DIR` (directory containing `config.yaml` and `compose.env`)

Related paths:
- Compose env file defaults to `~/.config/lasso/compose.env` (override with
  `LASSO_ENV_FILE` or `--env-file`)
- When running from source, set `LASSO_BUNDLE_DIR` to the repo root so the CLI
  can find the compose files

## Default config

```yaml
version: 1

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
```

## Field reference

### version
- **Type:** integer
- **Required:** yes
- **Meaning:** schema version. Must be `1`.

### paths.log_root
- **Type:** string (path)
- **Default:** `~/lasso-logs`
- **Meaning:** host directory where logs are written and mounted into containers.
- **Notes:** `lasso config apply` creates this directory if missing. A leading
  `~/` is expanded to your home directory.

### paths.workspace_root
- **Type:** string (path)
- **Default:** `~/lasso-workspace`
- **Meaning:** host directory mounted into the agent/harness as `/work`.
- **Notes:** `lasso config apply` creates this directory if missing. A leading
  `~/` is expanded to your home directory.

### release.tag
- **Type:** string
- **Default:** empty
- **Meaning:** container image tag to use for all services.
- **Behavior:**
  - If empty, the CLI uses its own version and prepends `v` (e.g. `v0.1.4`).
  - If set, this exact value is used for image tags (e.g. `v0.1.4`, `latest`).

### docker.project_name
- **Type:** string
- **Default:** `lasso`
- **Meaning:** Docker Compose project name (`docker compose -p`).
- **Effect:** changes container names, networks, and volume prefixes.

### harness.api_host
- **Type:** string (host/IP)
- **Default:** `127.0.0.1`
- **Meaning:** address the CLI uses to talk to the harness HTTP API.

### harness.api_port
- **Type:** integer
- **Default:** `8081`
- **Meaning:** port the CLI uses to talk to the harness HTTP API.
- **Note:** The default compose files bind the harness to `127.0.0.1:8081`.
  If you change this value, ensure the compose port binding matches.

### harness.api_token
- **Type:** string
- **Default:** empty
- **Meaning:** token required for `lasso run` (server mode jobs).
- **Note:** If empty, you can also provide `HARNESS_API_TOKEN` in the
  environment (or in the compose env file) instead.

## What `lasso config apply` does

`lasso config apply` validates the file and then:
1) Writes a compose env file (default `~/.config/lasso/compose.env`).
2) Creates `paths.log_root` and `paths.workspace_root` if missing.

The compose env file includes:
- `LASSO_VERSION` (from `release.tag` or CLI version)
- `LASSO_LOG_ROOT`
- `LASSO_WORKSPACE_ROOT`
- `HARNESS_API_TOKEN` (if set)
- `HARNESS_HTTP_PORT` (from `harness.api_port`)

## Validation rules

- Unknown fields are rejected.
- `version` must be `1`.
- `lasso config validate` and `lasso config apply` both enforce these rules.

## Common edits

### Change log/workspace locations
```yaml
paths:
  log_root: /Volumes/Lasso/logs
  workspace_root: /Volumes/Lasso/workspace
```

### Pin a specific release tag
```yaml
release:
  tag: v0.1.4
```
