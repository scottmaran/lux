# Harness

## Purpose
Trusted control plane that runs provider commands inside the `agent` container
over SSH, while capturing evidence logs:
- Interactive PTY sessions (TUI).
- Non-interactive jobs (HTTP API).

It also persists run markers (`root_pid`, `root_sid`) that the collector uses
for ownership attribution.

## Modes (Auto + Override)
Mode selection happens in `harness/entrypoint.sh`:
- If stdin is a TTY: `tui`
- Otherwise: `server`

Override with `HARNESS_MODE=tui|server`.

## Runtime Contract (Mounts, Network, Trust)
Mounts (container paths):
- `/work`: rw workspace
- `/logs`: rw log sink for harness (should be ro in `agent`)
- `/harness/keys`: rw shared key volume (ssh keypair, `authorized_keys`, `known_hosts`)

Network:
- SSH: harness -> agent on the compose network (no host port required)
- HTTP: binds `HARNESS_HTTP_BIND:HARNESS_HTTP_PORT` inside the harness container;
  host exposure is controlled by `compose.yml`

Trust boundary:
- No Docker socket required.
- SSH host key verification is disabled for the internal compose network
  (`StrictHostKeyChecking=no`).

## Key Handling (SSH Bootstrap)
On startup, `harness/entrypoint.sh` generates an ed25519 keypair in
`HARNESS_KEYS_DIR` (default `/harness/keys`) if missing, then ensures
`authorized_keys` contains the public key. The agent mounts this at
`/config/authorized_keys`.

## Quick Mental Model
TUI:
- `harness` allocates a local PTY (`forkpty`) and execs `ssh -tt ...` in the
  child.
- Parent proxies bytes between host stdin/stdout and the PTY, logging raw bytes
  to `stdin.log` and `stdout.log`.

Jobs:
- `POST /run` spawns a background thread that runs `ssh ... bash -lc <cmd>`.
- The remote command is wrapped with `setsid` so concurrent jobs get a stable
  per-run SID marker.

Attribution integration:
- Harness writes and persists `root_pid`/`root_sid`; collector uses those + audit
  exec lineage. See `docs/contracts/attribution.md`.

## Stage Map (Code + Tests)
| Concern | Code | Primary tests |
|---|---|---|
| Mode selection + key bootstrap | `harness/entrypoint.sh` | stack startup coverage (for example `tests/integration/test_run_scoped_log_layout.py`) |
| Marker helpers | `harness/harness.py` (`root_marker_prefix`, `read_remote_root_markers`, `wrap_with_setsid`) | `tests/unit/test_harness_markers.py` |
| Server API + job execution | `harness/harness.py` (`HarnessHandler`, `handle_run`, `run_job`) | `tests/integration/test_job_lifecycle_artifacts.py` |
| TUI PTY proxy | `harness/harness.py` (`run_tui`) | `tests/integration/test_agent_codex_tui.py`, `tests/integration/test_agent_codex_tui_concurrent.py` |
| Per-owner timeline copies | `harness/harness.py` (timeline copy + reconcile helpers) | `tests/integration/test_run_scoped_log_layout.py` |

## On-Disk Artifacts (External Contract)
The harness writes artifacts under `HARNESS_LOG_DIR`.

Run-scoped deployments set:
- `HARNESS_LOG_DIR=/logs/${LASSO_RUN_ID}/harness`

Sessions live under `.../sessions/<session_id>/...`, jobs under
`.../jobs/<job_id>/...`, and labels under `.../labels/...`.

Full on-disk contract:
- `docs/contracts/harness_artifacts.md`

## HTTP API (Server Mode)
Auth:
- Requests must include `X-Harness-Token` matching `HARNESS_API_TOKEN`.
- The harness refuses to start in server mode if `HARNESS_API_TOKEN` is unset.

Endpoints:
- `POST /run`: submit a job
- `GET /jobs/<id>`: in-memory status for a submitted job

Important limitation:
- `/jobs/<id>` does not load historical jobs from disk after a harness restart.

Full API contract:
- `docs/contracts/harness_api.md`

## Root Markers and Attribution Integration
Markers written by the harness:
- `root_pid`: namespaced PID for the run root process
- `root_sid`: namespaced Linux session ID (SID) for the run root process

Mechanics:
- Markers are written inside the agent container under `/tmp/` as
  `/tmp/lasso_root_pid_<id>.txt` and `/tmp/lasso_root_sid_<id>.txt`.
- Harness polls these marker files over SSH and patches `root_pid`/`root_sid`
  into job/session JSON.

Collector integration:
- See `docs/contracts/attribution.md`.

## Timeline Copy Materialization (Per Job/Session)
Input:
- `HARNESS_TIMELINE_PATH` (global merged timeline file).

Output:
- `sessions/<id>/filtered_timeline.jsonl` and `jobs/<id>/filtered_timeline.jsonl`
  are derived by filtering the global timeline by `session_id`/`job_id`.

Semantics:
- The collector merger rewrites the global timeline periodically.
- Harness reconciles per-owner copies by re-filtering until row count stabilizes
  (`HARNESS_TIMELINE_RECONCILE_PASSES`, `HARNESS_TIMELINE_RECONCILE_INTERVAL_SEC`).
- Treat per-owner copies as derived snapshot files, not append-only tails.

Related:
- `docs/contracts/schemas/timeline.filtered.v1.md` (timeline file semantics)

## Configuration (Env Vars)
Entrypoint (used by `harness/entrypoint.sh`):
- `HARNESS_MODE`
- `HARNESS_KEYS_DIR`
- `HARNESS_SSH_KEY_PATH`
- `HARNESS_AUTHORIZED_KEYS_PATH`

Runtime (used by `harness/harness.py`):
- SSH: `HARNESS_AGENT_HOST`, `HARNESS_AGENT_PORT`, `HARNESS_AGENT_USER`,
  `HARNESS_SSH_KEY_PATH`, `HARNESS_SSH_KNOWN_HOSTS`, `HARNESS_SSH_WAIT_SEC`
- API: `HARNESS_HTTP_BIND`, `HARNESS_HTTP_PORT`, `HARNESS_API_TOKEN`
- Commands: `HARNESS_TUI_CMD`, `HARNESS_TUI_NAME`, `HARNESS_RUN_CMD_TEMPLATE`
- Paths: `HARNESS_AGENT_WORKDIR`, `HARNESS_LOG_DIR`, `HARNESS_TIMELINE_PATH`
- Markers: `HARNESS_ROOT_PID_TIMEOUT_SEC`, `HARNESS_ROOT_PID_POLL_SEC`
- Timeline copy reconcile: `HARNESS_TIMELINE_RECONCILE_PASSES`,
  `HARNESS_TIMELINE_RECONCILE_INTERVAL_SEC`

Provider note:
- `HARNESS_TUI_CMD` and `HARNESS_RUN_CMD_TEMPLATE` are typically set by `lasso`
  provider runtime overrides (see `docs/contracts/config.md`).

## Troubleshooting
- Server won't start: `HARNESS_API_TOKEN` missing.
- Entrypoint fails early: `/logs` or `HARNESS_KEYS_DIR` not writable by uid 1002.
- Agent unreachable: check SSH readiness (`HARNESS_SSH_WAIT_SEC`), key volume
  wiring, and agent sshd.
- Missing `root_pid/root_sid`: remote `/tmp/lasso_root_*` files missing or marker
  capture timed out.
- Missing per-owner timeline rows: global timeline path mismatch, collector
  hasn't attributed rows yet, or reconcile window too short.

## Change Checklist (For PRs)
- If you change job/session JSON shapes: update `docs/contracts/harness_artifacts.md` and the
  corresponding integration assertions.
- If you change marker logic: update `tests/unit/test_harness_markers.py` and
  any attribution-sensitive integration/regression tests.
- If you change API behavior: update `docs/contracts/harness_api.md` and add/update integration
  coverage.
