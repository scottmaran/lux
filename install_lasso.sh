#!/usr/bin/env bash
set -euo pipefail

VERSION=""
INSTALL_DIR="${HOME}/.lasso"
BIN_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/lasso"

usage() {
  cat <<USAGE
Usage: install_lasso.sh --version vX.Y.Z [--install-dir PATH] [--bin-dir PATH] [--config-dir PATH]

Installs the Lasso CLI bundle without creating log/workspace directories.

Required:
  --version vX.Y.Z

Optional:
  --install-dir PATH   (default: ~/.lasso)
  --bin-dir PATH       (default: ~/.local/bin)
  --config-dir PATH    (default: ~/.config/lasso)
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version)
      VERSION="$2"; shift 2 ;;
    --install-dir)
      INSTALL_DIR="$2"; shift 2 ;;
    --bin-dir)
      BIN_DIR="$2"; shift 2 ;;
    --config-dir)
      CONFIG_DIR="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [ -z "$VERSION" ]; then
  echo "ERROR: --version is required" >&2
  usage
  exit 1
fi

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) ARCH="amd64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

BASE_URL="https://github.com/scottmaran/lasso/releases/download/${VERSION}"
VERSION_TAG=${VERSION#v}
BUNDLE="lasso_${VERSION_TAG}_${OS}_${ARCH}.tar.gz"
CHECKSUM="${BUNDLE}.sha256"

TMP_DIR=$(mktemp -d)

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

curl -fsSL "${BASE_URL}/${BUNDLE}" -o "${TMP_DIR}/${BUNDLE}"
curl -fsSL "${BASE_URL}/${CHECKSUM}" -o "${TMP_DIR}/${CHECKSUM}"

if command -v shasum >/dev/null 2>&1; then
  ( cd "$TMP_DIR" && shasum -a 256 -c "${CHECKSUM}" )
elif command -v sha256sum >/dev/null 2>&1; then
  ( cd "$TMP_DIR" && sha256sum -c "${CHECKSUM}" )
else
  echo "WARNING: no sha256 verifier found; skipping checksum verification." >&2
fi

DEST_DIR="${INSTALL_DIR}/versions/${VERSION_TAG}"
mkdir -p "$DEST_DIR"

tar -xzf "${TMP_DIR}/${BUNDLE}" -C "$DEST_DIR"

ln -sfn "$DEST_DIR" "${INSTALL_DIR}/current"

mkdir -p "$BIN_DIR"
ln -sfn "${INSTALL_DIR}/current/lasso" "${BIN_DIR}/lasso"

mkdir -p "$CONFIG_DIR"
if [ ! -f "${CONFIG_DIR}/config.yaml" ]; then
  cp "${INSTALL_DIR}/current/config/default.yaml" "${CONFIG_DIR}/config.yaml"
fi

cat <<EOFMSG
✅ Lasso installed.

Next steps:
1) Edit config: ${CONFIG_DIR}/config.yaml
   - Set paths.log_root and paths.workspace_root
2) Apply config: lasso config apply
3) Start stack:  lasso up
EOFMSG
