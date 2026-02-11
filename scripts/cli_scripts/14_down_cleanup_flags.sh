#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

require_cmd docker

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

cleanup() {
  lasso down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

lasso config apply
lasso up --wait --timeout-sec "${LASSO_WAIT_TIMEOUT_SEC:-120}"

volume_name="${LASSO_PROJECT_NAME}_harness_keys"
if ! docker volume ls --format '{{.Name}}' | grep -x "$volume_name" >/dev/null 2>&1; then
  echo "ERROR: expected volume to exist after up: $volume_name" >&2
  exit 1
fi

lasso down --volumes --remove-orphans

if docker volume ls --format '{{.Name}}' | grep -x "$volume_name" >/dev/null 2>&1; then
  echo "ERROR: expected volume to be removed by down --volumes: $volume_name" >&2
  exit 1
fi

status_json=$(lasso --json status)
count=$(echo "$status_json" | json_field result | json_len)
if [ "$count" -ne 0 ]; then
  echo "ERROR: expected no running containers after down" >&2
  echo "$status_json" >&2
  exit 1
fi

echo "ok"
