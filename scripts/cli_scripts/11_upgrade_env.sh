#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

# Apply v0.1.0
LASSO_VERSION="v0.1.0"
write_config "$LOG_ROOT" "$WORK_ROOT"
lasso config apply
content=$(cat "$ENV_FILE")
if [[ "$content" != *"LASSO_VERSION=v0.1.0"* ]]; then
  echo "ERROR: expected v0.1.0 in env file" >&2
  exit 1
fi

# Apply v0.1.1
LASSO_VERSION="v0.1.1"
write_config "$LOG_ROOT" "$WORK_ROOT"
lasso config apply
content=$(cat "$ENV_FILE")
if [[ "$content" != *"LASSO_VERSION=v0.1.1"* ]]; then
  echo "ERROR: expected v0.1.1 in env file" >&2
  exit 1
fi

echo "ok"
