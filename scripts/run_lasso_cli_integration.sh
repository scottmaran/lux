#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LASSO_BIN=${LASSO_BIN:-lasso}
LASSO_VERSION=${LASSO_VERSION:-v0.1.0}
HARNESS_API_TOKEN=${HARNESS_API_TOKEN:-dev-token}

if ! command -v "$LASSO_BIN" >/dev/null 2>&1; then
  echo "ERROR: lasso CLI not found in PATH. Set LASSO_BIN or install the CLI." >&2
  exit 1
fi

TMP_DIR=$(mktemp -d)
LOG_ROOT="$TMP_DIR/logs"
WORK_ROOT="$TMP_DIR/workspace"
ENV_FILE="$TMP_DIR/compose.env"
CONFIG_PATH="$TMP_DIR/config.yaml"

cat >"$CONFIG_PATH" <<CONFIG
version: 1
paths:
  log_root: $LOG_ROOT
  workspace_root: $WORK_ROOT
release:
  tag: "$LASSO_VERSION"
docker:
  project_name: lasso-test
harness:
  api_host: 127.0.0.1
  api_port: 8081
  api_token: "$HARNESS_API_TOKEN"
CONFIG

export LASSO_BUNDLE_DIR="$ROOT_DIR"
export LASSO_ENV_FILE="$ENV_FILE"
export HARNESS_RUN_CMD_TEMPLATE='echo stub-ok'
export HARNESS_TUI_CMD='bash -lc "echo stub-ok"'

"$LASSO_BIN" --config "$CONFIG_PATH" config apply

"$LASSO_BIN" --config "$CONFIG_PATH" up

sleep 5

if [ ! -s "$LOG_ROOT/audit.log" ]; then
  echo "ERROR: audit.log missing or empty" >&2
  exit 1
fi
if [ ! -s "$LOG_ROOT/ebpf.jsonl" ]; then
  echo "ERROR: ebpf.jsonl missing or empty" >&2
  exit 1
fi

RUN_OUTPUT=$($LASSO_BIN --config "$CONFIG_PATH" --json run "stub")
JOB_ID=$(python3 - <<'PY'
import json,sys
payload=json.loads(sys.stdin.read())
print(payload.get("result",{}).get("job_id",""))
PY
<<<"$RUN_OUTPUT")

if [ -z "$JOB_ID" ]; then
  echo "ERROR: job_id not found in run output" >&2
  echo "$RUN_OUTPUT" >&2
  exit 1
fi

if [ ! -s "$LOG_ROOT/jobs/$JOB_ID/input.json" ]; then
  echo "ERROR: job input.json missing" >&2
  exit 1
fi

if command -v script >/dev/null 2>&1; then
  script -q /dev/null "$LASSO_BIN" --config "$CONFIG_PATH" tui || true
fi

"$LASSO_BIN" --config "$CONFIG_PATH" down

echo "Lasso CLI integration smoke test complete."
