# Lasso

Agent Harness is an OS‑level observation system for third‑party agents: it runs the agent in a container, uses auditd + eBPF inside the Docker Desktop VM to capture exec/fs/network/IPC metadata, and correlates that into a session‑tagged timeline. The stack includes a harness (PTY + API), a collector pipeline (filter → summary → merge), a dedicated container to run the agent, and a UI for log review.

## Lasso CLI (beta)
The recommended way to run the stack is via the `lasso` CLI, which pulls the
versioned Docker images from GHCR and manages config + compose wiring.

### Install (beta)
Run the versioned installer:
```bash
curl -fsSL https://raw.githubusercontent.com/scottmaran/lasso/v0.1.4/install_lasso.sh | bash -s -- --version v0.1.4
```
This installs the CLI bundle but does **not** create log/workspace directories. Run `lasso config init` to create the default configurations, then edit `~/.config/lasso/config.yaml` to modify configs. You can customize `paths.log_root` and `paths.workspace_root`.
You must run `lasso config apply` to validate config values, write `~/.config/lasso/compose.env`, and create the configured log/workspace directories.

Quick start (after install):
```bash
lasso config init
lasso config apply
lasso up --codex
lasso tui --codex
```

To view more info about user configs, see `docs/guide/config.md`.

## Docs
Start with the user guide in `docs/guide/`.
Developers/contributors: see `docs/README.md` for the full documentation map.
