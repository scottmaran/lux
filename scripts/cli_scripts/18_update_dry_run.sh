#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

cleanup() {
  rm -rf "${TMP_DIR:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

INSTALL_DIR="$TMP_DIR/install"
BIN_DIR="$TMP_DIR/bin"
mkdir -p "$INSTALL_DIR/versions/0.1.0" "$BIN_DIR"
touch "$INSTALL_DIR/versions/0.1.0/lasso"
ln -sfn "$INSTALL_DIR/versions/0.1.0" "$INSTALL_DIR/current"
ln -sfn "$INSTALL_DIR/current/lasso" "$BIN_DIR/lasso"

output=$(LASSO_INSTALL_DIR="$INSTALL_DIR" LASSO_BIN_DIR="$BIN_DIR" \
  lasso --json update apply --to v9.9.9 --dry-run)

target=$(echo "$output" | json_field result.target_version)
if [ "$target" != "v9.9.9" ]; then
  echo "ERROR: expected target_version=v9.9.9, got $target" >&2
  echo "$output" >&2
  exit 1
fi
if [ ! -L "$INSTALL_DIR/current" ]; then
  echo "ERROR: dry-run should not mutate current symlink" >&2
  exit 1
fi

echo "ok"
