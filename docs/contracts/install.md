# Lasso Installation Guide
Layer: Contract

This guide covers both the recommended installer-script flow and a fully manual
installation for users who prefer not to run scripts.

## Prerequisites

- Docker installed and running:
  - macOS: Docker Desktop (supported).
  - Linux: may work, but is currently not guaranteed (see `docs/contracts/platform.md`).
- Access to GHCR for private images (run `docker login ghcr.io`).

## Install (Recommended)

Run the versioned installer:

```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lasso/${VERSION}/install_lasso.sh" | bash -s -- --version "${VERSION}"
```

To run the interactive setup wizard automatically after install:

```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lasso/${VERSION}/install_lasso.sh" | bash -s -- --version "${VERSION}" --setup
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

BUNDLE="lasso_${VERSION#v}_${OS}_${ARCH}.tar.gz"

gh auth login
gh release download "$VERSION" -R scottmaran/lasso -p "${BUNDLE}*" -D .
bash install_lasso.sh --version "$VERSION" \
  --bundle "${BUNDLE}" \
  --checksum "${BUNDLE}.sha256"
```

If you prefer to inspect the script first:

```bash
VERSION=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/scottmaran/lasso/${VERSION}/install_lasso.sh" -o install_lasso.sh
bash install_lasso.sh --version "${VERSION}"
```

This:
- Installs the CLI bundle under `~/.lasso/versions/<ver>`
- Creates `~/.lasso/current` symlink
- Installs `lasso` into `~/.local/bin`
- Creates `~/.config/lasso/config.yaml` if missing

**Note:** The installer does **not** create log/workspace directories. The
recommended next step is `lasso setup`, which configures paths + auth and runs
`lasso config apply` for you.

If `lasso` is "command not found" after install, ensure `~/.local/bin` is in
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
BUNDLE="lasso_${VERSION_TAG}_${OS}_${ARCH}.tar.gz"
curl -fsSL "https://github.com/scottmaran/lasso/releases/download/${VERSION}/${BUNDLE}" -o "${BUNDLE}"
```

2) (Optional) Verify checksum:

```bash
curl -fsSL "https://github.com/scottmaran/lasso/releases/download/${VERSION}/${BUNDLE}.sha256" -o "${BUNDLE}.sha256"
shasum -a 256 -c "${BUNDLE}.sha256"
```

3) Extract to a versioned install dir:

```bash
mkdir -p ~/.lasso/versions/"${VERSION_TAG}"
tar -xzf "${BUNDLE}" --strip-components=1 -C ~/.lasso/versions/"${VERSION_TAG}"
```

4) Create symlinks:

```bash
ln -sfn ~/.lasso/versions/"${VERSION_TAG}" ~/.lasso/current
mkdir -p ~/.local/bin
ln -sfn ~/.lasso/current/lasso ~/.local/bin/lasso
```

5) Initialize config (if missing):

```bash
mkdir -p ~/.config/lasso
cp ~/.lasso/current/config/default.yaml ~/.config/lasso/config.yaml
```

## Configure + Run

1) Run the setup wizard (recommended):

```bash
lasso setup
```

This updates `~/.config/lasso/config.yaml` in place and can optionally create
provider secrets files (API-key mode).

2) Start stack:

```bash
lasso up --collector-only --wait
lasso up --provider codex --wait
lasso tui --provider codex
```

### Manual config (no wizard)

```bash
$EDITOR ~/.config/lasso/config.yaml
lasso config apply
lasso up --collector-only --wait
lasso up --provider codex --wait
lasso tui --provider codex
```

3) Run a job (optional):

```bash
lasso run --provider codex "hello"
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
lasso update apply --to vX.Y.Z --dry-run
```

## GHCR Authentication (Private Images)

If images are private, authenticate once:

```bash
docker login ghcr.io
```

After login, Docker will automatically use stored credentials when pulling
images for `lasso up`.
