#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

require_cmd docker

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

cleanup() {
  "$LASSO_BIN" --config "$CONFIG_PATH" down --provider codex >/dev/null 2>&1 || true
  "$LASSO_BIN" --config "$CONFIG_PATH" down --collector-only >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

image="ghcr.io/scottmaran/lasso-harness:${LASSO_VERSION}"
if docker pull "$image" >/dev/null 2>&1; then
  echo "SKIP: already authenticated to GHCR; log out to test this case."
  exit 0
fi

set +e
output=$("$LASSO_BIN" --config "$CONFIG_PATH" up --collector-only 2>&1)
status=$?
if [ $status -eq 0 ]; then
  output=$("$LASSO_BIN" --config "$CONFIG_PATH" up --provider codex 2>&1)
  status=$?
fi
set -e

if [ $status -eq 0 ]; then
  echo "SKIP: lasso up succeeded (likely local image cache); cannot assert GHCR auth failure."
  exit 0
fi

if ! echo "$output" | grep -iE "denied|unauthorized|authentication" >/dev/null 2>&1; then
  echo "ERROR: expected auth-related failure message" >&2
  echo "$output" >&2
  exit 1
fi

echo "ok"
