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
  - Runtime writes are run-scoped under `lasso__YYYY_MM_DD_HH_MM_SS/` directories
    (created by `lasso up`).

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

## HARNESS_API_TOKEN Details

`HARNESS_API_TOKEN` is the shared secret that protects the harness HTTP API
used for non-interactive runs (`lasso run`).

- **Why it exists:** The harness runs a small local web service on your computer
  (only reachable from the same machine). It has two main endpoints:
  - `POST /run` starts a new non‑interactive job.
  - `GET /jobs/<id>` lets you check that job’s status and results.
- **What the token protects:** Think of the token like a password for that local
  service. Without it, any other program on your computer could send “start a
  job” requests to the harness. The token makes sure only you (or the `lasso`
  CLI you launched) can trigger runs.
- **Where it’s used:** The harness server checks the `X-Harness-Token` request
  header against `HARNESS_API_TOKEN`. The CLI reads `harness.api_token` from
  `config.yaml` and includes it when calling the API.
- **Why it’s in config:** Putting it in `config.yaml` ensures `lasso config apply`
  writes it into `compose.env`, so the harness container and the CLI share the
  same value.
- **If you don’t set it:**
  - `lasso run` fails with an error (token required).
  - The harness refuses to start in server mode without a token.
  - API requests without the header are rejected with `401 unauthorized`.
- **What to set it to:** Any non-empty string works, but use a long random value
  (e.g. 32+ chars). Example:
  ```bash
  openssl rand -hex 32
  ```

Notes:
- This token is only for the local harness API; it is unrelated to GHCR auth or
  SSH keys.
- TUI/interactive sessions do not require this token.

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
