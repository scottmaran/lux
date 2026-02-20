# Lux

Use claude code but worried about it making breaking changes to your computer? Come back to your laptop after a long agent run wondering what's changed?

If only there were something watching everything your agents did so you didn't miss anything important.

## About

Lux is an OS‑level observation system for third‑party agents: it runs the agent in a container, uses auditd + eBPF inside the Docker Desktop VM to capture exec/fs/network/IPC metadata, and correlates that into a session‑tagged timeline. The stack includes a harness (PTY + API), a collector pipeline (filter → summary → merge), a dedicated container to run the agent, and a UI for log review.

## Lux CLI (beta)
The recommended way to run the stack is via the `lux` CLI, which pulls the
versioned Docker images from GHCR and manages config + compose wiring.

Temporary support note (February 2026): 
- Linux host runtime support is temporarily not guaranteed while bind-mount permission compatibility work is in progress. The currently recommended host is macOS with Docker Desktop.
- For subscription-based Claude Code sessions on MacOS, you need to log in upon starting the TUI
See platform support/caveats: `docs/contracts/platform.md`.

### Install (beta)
Run the versioned installer:
```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lux/${VERSION}/install_lux.sh" | bash -s -- --version "${VERSION}"
```
To run the interactive setup wizard automatically after install:
```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lux/${VERSION}/install_lux.sh" | bash -s -- --version "${VERSION}" --setup
```

If `lux` is "command not found" after install, ensure `~/.local/bin` is in your `PATH`.
This installs the CLI bundle but does **not** create runtime directories. Run `lux setup` to configure `config.yaml` (paths + provider auth) and generate the runtime env file (`<trusted_root>/state/compose.env` by default).

Quick start (after install):
```bash
lux setup
lux runtime up
lux ui up --wait
lux shim install
codex
```

Provider selection is explicit for agent-facing actions (`--provider codex|claude`).
Collector lifecycle is separate (`--collector-only`).

To view more info about user configs, see `docs/contracts/config.md`.

## Run-scoped logs
Each `lux up` creates a new run directory under `paths.log_root`, for example:

```text
<trusted_root>/logs/
  lux__2026_02_12_12_23_54/
    collector/raw/
    collector/filtered/
    harness/sessions/
    harness/jobs/
    harness/labels/
```

`lux logs tail` and `lux jobs ...` default to the active run. If no run is
active, use `--run-id <id>` or `--latest`.

## Docs
Start with the user guide in `docs/contracts/`.
Developers/contributors: see `docs/README.md` for the full documentation map.

## License
Licensed under the GNU Affero General Public License v3.0 only (`AGPL-3.0-only`).
See `LICENSE`.
