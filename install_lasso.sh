#!/usr/bin/env bash
set -euo pipefail

VERSION=""
BUNDLE_PATH=""
CHECKSUM_PATH=""

usage() {
  cat <<USAGE
Usage: install_lasso.sh --version vX.Y.Z [--bundle <path>] [--checksum <path>]

Installs the Lasso CLI bundle without creating log/workspace directories.

Required:
  --version vX.Y.Z

Optional (offline / private repo flow):
  --bundle <path>    Local path to the release bundle tarball
                     (must be named like lasso_<ver>_<os>_<arch>.tar.gz)
  --checksum <path>  Local path to the checksum file for the tarball
                     (must be named like lasso_<ver>_<os>_<arch>.tar.gz.sha256)

Environment:
  LASSO_RELEASE_BASE_URL  Base URL for release downloads
                          (default: https://github.com/scottmaran/lasso/releases/download)
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version)
      VERSION="$2"; shift 2 ;;
    --bundle)
      BUNDLE_PATH="$2"; shift 2 ;;
    --checksum)
      CHECKSUM_PATH="$2"; shift 2 ;;
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

if [ -n "$CHECKSUM_PATH" ] && [ -z "$BUNDLE_PATH" ]; then
  echo "ERROR: --checksum requires --bundle" >&2
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

RELEASE_BASE_URL="${LASSO_RELEASE_BASE_URL:-https://github.com/scottmaran/lasso/releases/download}"
BASE_URL="${RELEASE_BASE_URL%/}/${VERSION}"
VERSION_TAG=${VERSION#v}
BUNDLE="lasso_${VERSION_TAG}_${OS}_${ARCH}.tar.gz"
CHECKSUM="${BUNDLE}.sha256"

TMP_DIR=$(mktemp -d)

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

download() {
  local url="$1"
  local dest="$2"
  if ! curl -fsSL "$url" -o "$dest"; then
    echo "ERROR: download failed: $url" >&2
    echo "" >&2
    echo "If this repo (or its release assets) is private, GitHub may return 404 for unauthenticated downloads." >&2
    echo "Options:" >&2
    echo "  1) Use GitHub CLI to download assets, then re-run with --bundle/--checksum" >&2
    echo "  2) Host release artifacts elsewhere and set LASSO_RELEASE_BASE_URL" >&2
    exit 1
  fi
}

if [ -n "$BUNDLE_PATH" ]; then
  if [ ! -f "$BUNDLE_PATH" ]; then
    echo "ERROR: bundle not found: $BUNDLE_PATH" >&2
    exit 1
  fi
  if [ "$(basename "$BUNDLE_PATH")" != "$BUNDLE" ]; then
    echo "ERROR: bundle filename mismatch for this platform/version." >&2
    echo "  expected: $BUNDLE" >&2
    echo "  got:      $(basename "$BUNDLE_PATH")" >&2
    exit 1
  fi
  cp "$BUNDLE_PATH" "${TMP_DIR}/${BUNDLE}"
  if [ -n "$CHECKSUM_PATH" ]; then
    if [ ! -f "$CHECKSUM_PATH" ]; then
      echo "ERROR: checksum not found: $CHECKSUM_PATH" >&2
      exit 1
    fi
    if [ "$(basename "$CHECKSUM_PATH")" != "$CHECKSUM" ]; then
      echo "ERROR: checksum filename mismatch for this platform/version." >&2
      echo "  expected: $CHECKSUM" >&2
      echo "  got:      $(basename "$CHECKSUM_PATH")" >&2
      exit 1
    fi
    cp "$CHECKSUM_PATH" "${TMP_DIR}/${CHECKSUM}"
  fi
else
  download "${BASE_URL}/${BUNDLE}" "${TMP_DIR}/${BUNDLE}"
  download "${BASE_URL}/${CHECKSUM}" "${TMP_DIR}/${CHECKSUM}"
fi

if [ -f "${TMP_DIR}/${CHECKSUM}" ]; then
  if command -v shasum >/dev/null 2>&1; then
    ( cd "$TMP_DIR" && shasum -a 256 -c "${CHECKSUM}" )
  elif command -v sha256sum >/dev/null 2>&1; then
    ( cd "$TMP_DIR" && sha256sum -c "${CHECKSUM}" )
  else
    echo "WARNING: no sha256 verifier found; skipping checksum verification." >&2
  fi
else
  echo "WARNING: checksum file not provided; skipping checksum verification." >&2
fi

INSTALL_DIR="${HOME}/.lasso"
BIN_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/lasso"
DEST_DIR="${INSTALL_DIR}/versions/${VERSION_TAG}"
mkdir -p "$DEST_DIR"

tar -xzf "${TMP_DIR}/${BUNDLE}" -C "$DEST_DIR"

# The release workflow tars a top-level directory (`lasso_<ver>_<os>_<arch>/...`).
# Flatten that directory into DEST_DIR so `DEST_DIR/lasso` exists.
if [ ! -f "${DEST_DIR}/lasso" ]; then
  dir_count=$(find "$DEST_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
  non_dir_count=$(find "$DEST_DIR" -mindepth 1 -maxdepth 1 ! -type d | wc -l | tr -d ' ')
  if [ "${dir_count}" -eq 1 ] && [ "${non_dir_count}" -eq 0 ]; then
    inner_dir=$(find "$DEST_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    shopt -s dotglob nullglob
    mv "${inner_dir}"/* "$DEST_DIR"/
    shopt -u dotglob nullglob
    rmdir "${inner_dir}"
  fi
fi

if [ ! -f "${DEST_DIR}/lasso" ]; then
  echo "ERROR: extracted bundle did not contain expected CLI binary at: ${DEST_DIR}/lasso" >&2
  exit 1
fi

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
