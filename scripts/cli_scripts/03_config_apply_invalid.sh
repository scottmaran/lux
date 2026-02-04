#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
cat >"$CONFIG_PATH" <<CONFIG
version: 1
unknown: true
CONFIG

output=$(expect_fail "$LASSO_BIN" --json --config "$CONFIG_PATH" config apply)
error=$(echo "$output" | json_field error)
if [[ "$error" != *"config is invalid"* ]] || [[ "$error" != *"Please edit"* ]]; then
  echo "ERROR: expected actionable invalid config message, got: $error" >&2
  exit 1
fi

echo "ok"
