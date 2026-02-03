# Harness container

Purpose: run the trusted control plane that launches Codex in the agent container and captures session logs. It supports:
- Interactive TUI sessions over SSH (PTY).
- Non-interactive runs via a local HTTP API that triggers `codex exec` in the agent.

## Contract
- `/work` is the shared workspace (bind-mount from host).
- `/logs` is the host sink (harness writes logs).
- `/harness/keys` is a shared volume with the agent; it contains `authorized_keys` and the harness SSH keypair.
- The harness connects to the agent via SSH on the compose network (no host port required).

## Key handling
On startup, the harness generates an ed25519 keypair in `/harness/keys` if one does not exist, then writes the public key to
`/harness/keys/authorized_keys`. The agent mounts this file at `/config/authorized_keys`.

## Modes
The entrypoint chooses a mode automatically:
- If stdin is a TTY, it runs `tui`.
- Otherwise it runs `server`.

You can override with `HARNESS_MODE=tui` or `HARNESS_MODE=server`.

### TUI mode
Launches Codex via `ssh -tt agent@agent` and proxies stdin/stdout through a PTY, logging both streams:
- `logs/sessions/<session_id>/stdin.log`
- `logs/sessions/<session_id>/stdout.log`
- `logs/sessions/<session_id>/tui.cast` (asciinema v2, for replay)

By default the TUI uses `/work` as the working root and disables Codex sandboxing (`codex -C /work -s danger-full-access`).
You can override the command with `HARNESS_TUI_CMD`.
You can optionally set a human-friendly TUI name via `HARNESS_TUI_NAME` or pass `--tui-name` when invoking `harness.py` directly.

### Server mode
Exposes a minimal HTTP API for non-interactive runs:
- `POST /run` triggers the configured run command in the agent via SSH.
- `GET /jobs/<id>` returns job status.

Use `HARNESS_HTTP_BIND` and `HARNESS_HTTP_PORT` to control the listen address.
Requests must include `X-Harness-Token` matching `HARNESS_API_TOKEN`.

The run command is controlled by `HARNESS_RUN_CMD_TEMPLATE` (default: `codex -C /work -s danger-full-access exec {prompt}`).
The `{prompt}` placeholder is replaced with a shell-quoted prompt; omit the placeholder to ignore the prompt.
You can optionally include a `name` field in the `/run` payload to create a display label for the job.

## Environment
- `HARNESS_AGENT_HOST` (default: `agent`)
- `HARNESS_AGENT_PORT` (default: `22`)
- `HARNESS_AGENT_USER` (default: `agent`)
- `HARNESS_SSH_KEY_PATH` (default: `/harness/keys/ssh_key`)
- `HARNESS_SSH_WAIT_SEC` (default: `30`)
- `HARNESS_HTTP_BIND` (default: `0.0.0.0`)
- `HARNESS_HTTP_PORT` (default: `8081`)
- `HARNESS_API_TOKEN` (required for server mode)
- `HARNESS_TUI_CMD` (default: `codex -C /work -s danger-full-access`)
- `HARNESS_TUI_NAME` (optional: display label for TUI sessions)
- `HARNESS_RUN_CMD_TEMPLATE` (default: `codex -C /work -s danger-full-access exec {prompt}`)
- `HARNESS_AGENT_WORKDIR` (default: `/work`)

## Security posture
- No Docker socket required; SSH is used for control-plane access.
- Keys are internal to the harness/agent volume and not dependent on host files.
- `/logs` should be writable by the harness and read-only for the agent.
  - If you use the default `harness` user (uid 1002), ensure `./logs` is writable by that uid.
