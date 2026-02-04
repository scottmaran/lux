#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

output=$(PATH="" "$LASSO_BIN" --json --config "$CONFIG_PATH" doctor)
ok=$(echo "$output" | json_field ok)
error=$(echo "$output" | json_field error)

if [ "$ok" != "False" ] && [ "$ok" != "false" ]; then
  echo "ERROR: expected doctor ok=false" >&2
  exit 1
fi
if [[ "$error" != *"docker"* ]]; then
  echo "ERROR: expected docker error, got: $error" >&2
  exit 1
fi

echo "ok"
