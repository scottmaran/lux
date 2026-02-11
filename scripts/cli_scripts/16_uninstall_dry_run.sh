#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

cleanup() {
  rm -rf "${TMP_DIR:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

lasso config apply

INSTALL_DIR="$TMP_DIR/install"
BIN_DIR="$TMP_DIR/bin"
VERSION_DIR="$INSTALL_DIR/versions/0.1.0"
CURRENT_LINK="$INSTALL_DIR/current"
BIN_LINK="$BIN_DIR/lasso"

mkdir -p "$VERSION_DIR" "$BIN_DIR"
touch "$VERSION_DIR/lasso"
ln -sfn "$VERSION_DIR" "$CURRENT_LINK"
ln -sfn "$CURRENT_LINK/lasso" "$BIN_LINK"

output=$(LASSO_INSTALL_DIR="$INSTALL_DIR" LASSO_BIN_DIR="$BIN_DIR" \
  lasso --json uninstall --dry-run --remove-config --remove-data --all-versions --force)
dry_run=$(echo "$output" | json_field result.dry_run)
if [ "$dry_run" != "True" ] && [ "$dry_run" != "true" ]; then
  echo "ERROR: expected dry_run=true in uninstall output" >&2
  echo "$output" >&2
  exit 1
fi

if [ ! -L "$BIN_LINK" ]; then
  echo "ERROR: expected binary symlink to remain after dry-run" >&2
  exit 1
fi
if [ ! -L "$CURRENT_LINK" ]; then
  echo "ERROR: expected current symlink to remain after dry-run" >&2
  exit 1
fi
if [ ! -d "$INSTALL_DIR/versions" ]; then
  echo "ERROR: expected versions directory to remain after dry-run" >&2
  exit 1
fi
if [ ! -f "$CONFIG_PATH" ] || [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: expected config/env files to remain after dry-run" >&2
  exit 1
fi
if [ ! -d "$LOG_ROOT" ] || [ ! -d "$WORK_ROOT" ]; then
  echo "ERROR: expected data directories to remain after dry-run" >&2
  exit 1
fi

echo "ok"
