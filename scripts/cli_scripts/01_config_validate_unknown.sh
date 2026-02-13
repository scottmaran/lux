#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
cat >"$CONFIG_PATH" <<CONFIG
version: 2
unknown_field: true
paths:
  log_root: $LOG_ROOT
  workspace_root: $WORK_ROOT
CONFIG

output=$(expect_fail "$LASSO_BIN" --json --config "$CONFIG_PATH" config validate)
error=$(echo "$output" | json_field error)
if [[ "$error" != *"unknown"* ]]; then
  echo "ERROR: expected unknown field error, got: $error" >&2
  exit 1
fi

echo "ok"
