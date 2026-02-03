#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

require_cmd docker

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

image="ghcr.io/scottmaran/lasso-harness:${LASSO_VERSION}"
if docker pull "$image" >/dev/null 2>&1; then
  echo "SKIP: already authenticated to GHCR; log out to test this case."
  exit 0
fi

output=$(expect_fail "$LASSO_BIN" --config "$CONFIG_PATH" up)
if ! echo "$output" | grep -iE "denied|unauthorized|authentication" >/dev/null 2>&1; then
  echo "ERROR: expected auth-related failure message" >&2
  echo "$output" >&2
  exit 1
fi

echo "ok"
