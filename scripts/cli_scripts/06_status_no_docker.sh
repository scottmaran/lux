#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

if PATH="" "$LASSO_BIN" --config "$CONFIG_PATH" status --collector-only >/dev/null 2>&1; then
  echo "ERROR: expected status to fail without docker" >&2
  exit 1
fi

echo "ok"
