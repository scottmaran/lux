# Lux Installation Guide
Layer: Contract

This guide covers both the recommended installer-script flow and a fully manual
installation for users who prefer not to run scripts.

## Prerequisites

- Docker installed and running:
  - macOS: Docker Desktop.
  - Linux: Docker Engine or Docker Desktop.
- Access to GHCR for private images (run `docker login ghcr.io`).

## Install (Recommended)

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

If the repo (or release assets) are private, unauthenticated `curl` downloads
may return 404. In that case, download the release bundle with GitHub CLI and
install from the local tarball:

```bash
VERSION=vX.Y.Z
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) ARCH="amd64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

BUNDLE="lux_${VERSION#v}_${OS}_${ARCH}.tar.gz"

gh auth login
gh release download "$VERSION" -R scottmaran/lux -p "${BUNDLE}*" -D .
bash install_lux.sh --version "$VERSION" \
  --bundle "${BUNDLE}" \
  --checksum "${BUNDLE}.sha256"
```

If you prefer to inspect the script first:

```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lux/${VERSION}/install_lux.sh" -o install_lux.sh
bash install_lux.sh --version "${VERSION}"
```

This:
- Installs the CLI bundle under `~/.lux/versions/<ver>`
- Creates `~/.lux/current` symlink
- Installs `lux` into `~/.local/bin`
- Creates `~/.config/lux/config.yaml` (via `lux config init`) if missing

**Note:** The installer does **not** create log/workspace directories. The
recommended next step is `lux setup`, which configures paths + auth and runs
`lux config apply` for you.
By default, setup uses:
- workspace=`$HOME`
- trusted root outside `$HOME` (`/Users/Shared/Lux` on macOS, `/var/lib/lux` on Linux)
- log root at `<trusted_root>/logs`
- shim bin dir at `<trusted_root>/bin`

If `lux` is "command not found" after install, ensure `~/.local/bin` is in
your `PATH`.

## Manual Install (No Script)

1) Download the correct bundle for your OS/arch:

```bash
VERSION=vX.Y.Z
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) ARCH="amd64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

VERSION_TAG=${VERSION#v}
BUNDLE="lux_${VERSION_TAG}_${OS}_${ARCH}.tar.gz"
curl -fsSL "https://github.com/scottmaran/lux/releases/download/${VERSION}/${BUNDLE}" -o "${BUNDLE}"
```

2) (Optional) Verify checksum:

```bash
curl -fsSL "https://github.com/scottmaran/lux/releases/download/${VERSION}/${BUNDLE}.sha256" -o "${BUNDLE}.sha256"
shasum -a 256 -c "${BUNDLE}.sha256"
```

3) Extract to a versioned install dir:

```bash
mkdir -p ~/.lux/versions/"${VERSION_TAG}"
tar -xzf "${BUNDLE}" --strip-components=1 -C ~/.lux/versions/"${VERSION_TAG}"
```

4) Create symlinks:

```bash
ln -sfn ~/.lux/versions/"${VERSION_TAG}" ~/.lux/current
mkdir -p ~/.local/bin
ln -sfn ~/.lux/current/lux ~/.local/bin/lux
```

5) Initialize config (if missing):

```bash
mkdir -p ~/.config/lux
~/.local/bin/lux --config ~/.config/lux/config.yaml config init
```

## Configure + Run

1) Run the setup wizard (recommended):

```bash
lux setup
```

This updates `~/.config/lux/config.yaml` in place and can optionally create
provider secrets files (API-key mode). In interactive mode, setup also offers:
- optional shim enablement
- optional safer auto-start (collector refresh + UI up; no provider auto-start)

2) If you skipped startup/shims in setup, start stack manually:

```bash
lux up --collector-only --wait
lux ui up --wait
lux shim enable
codex
```

### Manual config (no wizard)

```bash
$EDITOR ~/.config/lux/config.yaml
lux config apply
lux up --collector-only --wait
lux up --provider codex --wait
lux tui --provider codex
```

3) Run a job (optional):

```bash
lux run --provider codex "hello"
```

## Updating

Check for updates:
```bash
lux update check
```

Apply latest release:
```bash
lux update apply --yes
```

Preview an update without changes:
```bash
lux update apply --to vX.Y.Z --dry-run
```

## GHCR Authentication (Private Images)

If images are private, authenticate once:

```bash
docker login ghcr.io
```

After login, Docker will automatically use stored credentials when pulling
images for `lux up`.
