#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

lasso config apply

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: compose env file missing" >&2
  exit 1
fi

content=$(cat "$ENV_FILE")
if [[ "$content" != *"LASSO_VERSION="* ]]; then
  echo "ERROR: LASSO_VERSION missing in env file" >&2
  exit 1
fi
if [[ "$content" != *"LASSO_LOG_ROOT="* ]]; then
  echo "ERROR: LASSO_LOG_ROOT missing in env file" >&2
  exit 1
fi
if [[ "$content" != *"LASSO_WORKSPACE_ROOT="* ]]; then
  echo "ERROR: LASSO_WORKSPACE_ROOT missing in env file" >&2
  exit 1
fi

if [ ! -d "$LOG_ROOT" ]; then
  echo "ERROR: log root not created" >&2
  exit 1
fi
if [ ! -d "$WORK_ROOT" ]; then
  echo "ERROR: workspace root not created" >&2
  exit 1
fi

echo "ok"
