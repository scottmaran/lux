# Harness container

Purpose: run the trusted control plane that launches provider commands in the agent container and captures session logs. It supports:
- Interactive TUI sessions over SSH (PTY).
- Non-interactive runs via a local HTTP API.

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
Launches the configured provider TUI command via `ssh -tt agent@agent` and proxies stdin/stdout through a PTY, logging both streams:
- `logs/<run_id>/harness/sessions/<session_id>/stdin.log`
- `logs/<run_id>/harness/sessions/<session_id>/stdout.log`
- `logs/<run_id>/harness/sessions/<session_id>/filtered_timeline.jsonl`
- `logs/<run_id>/harness/sessions/<session_id>/meta.json` (includes `root_pid` + `root_sid` run markers)

By default the TUI command is `bash -l`.
You can override the command with `HARNESS_TUI_CMD`.
You can optionally set a human-friendly TUI name via `HARNESS_TUI_NAME` or pass `--tui-name` when invoking `harness.py` directly.

### Server mode
Exposes a minimal HTTP API for non-interactive runs:
- `POST /run` triggers the configured run command template in the agent via SSH.
- `GET /jobs/<id>` returns job status.

Use `HARNESS_HTTP_BIND` and `HARNESS_HTTP_PORT` to control the listen address.
Requests must include `X-Harness-Token` matching `HARNESS_API_TOKEN`.

The run command is controlled by `HARNESS_RUN_CMD_TEMPLATE` (default: `bash -lc {prompt}`).
The `{prompt}` placeholder is replaced with a shell-quoted prompt; omit the placeholder to ignore the prompt.
You can optionally include a `name` field in the `/run` payload to create a display label for the job.

Both TUI sessions and `/run` jobs persist root run markers:
- `root_pid`: namespaced PID for the run root process.
- `root_sid`: namespaced Linux session ID (`SID`) for the run root process.

Non-interactive `/run` launch paths use `setsid` so concurrent jobs get a stable per-run SID marker.
TUI runs keep the native SSH PTY launch path and capture the corresponding PTY session SID.

## Environment
- `HARNESS_AGENT_HOST` (default: `agent`)
- `HARNESS_AGENT_PORT` (default: `22`)
- `HARNESS_AGENT_USER` (default: `agent`)
- `HARNESS_SSH_KEY_PATH` (default: `/harness/keys/ssh_key`)
- `HARNESS_SSH_WAIT_SEC` (default: `30`)
- `HARNESS_HTTP_BIND` (default: `0.0.0.0`)
- `HARNESS_HTTP_PORT` (default: `8081`)
- `HARNESS_API_TOKEN` (required for server mode)
- `HARNESS_TUI_CMD` (default: `bash -l`)
- `HARNESS_TUI_NAME` (optional: display label for TUI sessions)
- `HARNESS_RUN_CMD_TEMPLATE` (default: `bash -lc {prompt}`)
- `HARNESS_AGENT_WORKDIR` (default: `/work`)
- `HARNESS_LOG_DIR` (default: `/logs`)
- `HARNESS_TIMELINE_PATH` (default: `/logs/filtered_timeline.jsonl`)

For run-scoped deployments, set:
- `HARNESS_LOG_DIR=/logs/${LASSO_RUN_ID}/harness`
- `HARNESS_TIMELINE_PATH=/logs/${LASSO_RUN_ID}/collector/filtered/filtered_timeline.jsonl`

## Security posture
- No Docker socket required; SSH is used for control-plane access.
- Keys are internal to the harness/agent volume and not dependent on host files.
- `/logs` should be writable by the harness and read-only for the agent.
  - If you use the default `harness` user (uid 1002), ensure `./logs` is writable by that uid.
