#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

TMP_DIR=$(mktemp -d)
CONFIG_DIR="$TMP_DIR/config"

output=$(
  LASSO_CONFIG_DIR="$CONFIG_DIR" \
  "$LASSO_BIN" --json config init
)
created=$(echo "$output" | json_field result.created)
if [ "$created" != "True" ] && [ "$created" != "true" ]; then
  echo "ERROR: expected config to be created" >&2
  exit 1
fi

CONFIG_PATH="$CONFIG_DIR/config.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: config.yaml not created" >&2
  exit 1
fi

echo "sentinel: true" >"$CONFIG_PATH"

output=$(
  LASSO_CONFIG_DIR="$CONFIG_DIR" \
  "$LASSO_BIN" --json config init
)
created=$(echo "$output" | json_field result.created)
if [ "$created" != "False" ] && [ "$created" != "false" ]; then
  echo "ERROR: expected config init to preserve existing file" >&2
  exit 1
fi

content=$(cat "$CONFIG_PATH")
if [ "$content" != "sentinel: true" ]; then
  echo "ERROR: config init overwrote existing file" >&2
  exit 1
fi

echo "ok"
