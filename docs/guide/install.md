# Lasso Installation Guide

This guide covers both the recommended installer-script flow and a fully manual
installation for users who prefer not to run scripts.

## Prerequisites

- Docker Desktop (or Docker Engine) installed and running.
- Access to GHCR for private images (run `docker login ghcr.io`).

## Install (Recommended)

Run the versioned installer:

```bash
curl -fsSL https://raw.githubusercontent.com/scottmaran/lasso/v0.1.4/install_lasso.sh | bash -s -- --version v0.1.4
```

If you prefer to inspect the script first:

```bash
curl -fsSL https://raw.githubusercontent.com/scottmaran/lasso/v0.1.4/install_lasso.sh -o install_lasso.sh
bash install_lasso.sh --version v0.1.4
```

This:
- Installs the CLI bundle under `~/.lasso/versions/<ver>`
- Creates `~/.lasso/current` symlink
- Installs `lasso` into `~/.local/bin`
- Creates `~/.config/lasso/config.yaml` if missing

**Note:** The installer does **not** create log/workspace directories. You
choose those in the config.

## Manual Install (No Script)

1) Download the correct bundle for your OS/arch:

```bash
curl -fsSL https://github.com/scottmaran/lasso/releases/download/v0.1.4/lasso_0.1.4_darwin_arm64.tar.gz -o lasso.tar.gz
```

2) (Optional) Verify checksum:

```bash
curl -fsSL https://github.com/scottmaran/lasso/releases/download/v0.1.4/lasso_0.1.4_darwin_arm64.tar.gz.sha256 -o lasso.tar.gz.sha256
shasum -a 256 -c lasso.tar.gz.sha256
```

3) Extract to a versioned install dir:

```bash
mkdir -p ~/.lasso/versions/0.1.4
tar -xzf lasso.tar.gz -C ~/.lasso/versions/0.1.4
```

4) Create symlinks:

```bash
ln -sfn ~/.lasso/versions/0.1.4 ~/.lasso/current
mkdir -p ~/.local/bin
ln -sfn ~/.lasso/current/lasso ~/.local/bin/lasso
```

5) Initialize config (if missing):

```bash
mkdir -p ~/.config/lasso
cp ~/.lasso/current/config/default.yaml ~/.config/lasso/config.yaml
```

## Configure + Run

1) Edit config:

```bash
$EDITOR ~/.config/lasso/config.yaml
```

Set:
- `paths.log_root`
- `paths.workspace_root`

2) Apply config (creates directories + compose env file):

```bash
lasso config apply
```

3) Start stack:

```bash
lasso up
```

4) Run a job (optional):

```bash
lasso run "hello"
```

## Updating

Check for updates:
```bash
lasso update check
```

Apply latest release:
```bash
lasso update apply --yes
```

Preview an update without changes:
```bash
lasso update apply --to v0.1.5 --dry-run
```

## GHCR Authentication (Private Images)

If images are private, authenticate once:

```bash
docker login ghcr.io
```

After login, Docker will automatically use stored credentials when pulling
images for `lasso up`.
