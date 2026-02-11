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
mkdir -p "$INSTALL_DIR/versions/0.1.0" "$INSTALL_DIR/versions/0.2.0"
touch "$INSTALL_DIR/versions/0.1.0/lasso"
touch "$INSTALL_DIR/versions/0.2.0/lasso"
ln -sfn "$INSTALL_DIR/versions/0.2.0" "$INSTALL_DIR/current"

output=$(LASSO_INSTALL_DIR="$INSTALL_DIR" lasso --json update rollback --dry-run --previous)

target=$(echo "$output" | json_field result.target_version)
if [ "$target" != "v0.1.0" ]; then
  echo "ERROR: expected rollback target_version=v0.1.0, got $target" >&2
  echo "$output" >&2
  exit 1
fi
if [ "$(readlink "$INSTALL_DIR/current")" != "$INSTALL_DIR/versions/0.2.0" ]; then
  echo "ERROR: dry-run should not modify current symlink target" >&2
  exit 1
fi

echo "ok"
