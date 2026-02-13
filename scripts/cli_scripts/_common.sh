#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
LASSO_BIN=${LASSO_BIN:-lasso}
LASSO_VERSION=${LASSO_VERSION:-v0.1.0}
HARNESS_API_TOKEN=${HARNESS_API_TOKEN:-dev-token}
LASSO_PROJECT_NAME=${LASSO_PROJECT_NAME:-}
CONFIG_PATH=""
ENV_FILE=""
LOG_ROOT=""
WORK_ROOT=""

unset LASSO_CONFIG
unset LASSO_CONFIG_DIR
unset LASSO_ENV_FILE

export LASSO_BUNDLE_DIR=${LASSO_BUNDLE_DIR:-$ROOT_DIR}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required command: $1" >&2
    exit 1
  fi
}

setup_env() {
  TMP_DIR=$(mktemp -d)
  if [ -z "$LASSO_PROJECT_NAME" ]; then
    LASSO_PROJECT_NAME="lasso-test-$(basename "$TMP_DIR")"
  fi
  LOG_ROOT="$TMP_DIR/logs"
  WORK_ROOT="$TMP_DIR/workspace"
  ENV_FILE="$TMP_DIR/compose.env"
  CONFIG_PATH="$TMP_DIR/config.yaml"
  export LASSO_ENV_FILE="$ENV_FILE"
}

write_config() {
  local log_root="$1"
  local work_root="$2"
  cat >"$CONFIG_PATH" <<CONFIG
version: 2
paths:
  log_root: $log_root
  workspace_root: $work_root
release:
  tag: "$LASSO_VERSION"
docker:
  project_name: $LASSO_PROJECT_NAME
harness:
  api_host: 127.0.0.1
  api_port: 8081
  api_token: "$HARNESS_API_TOKEN"
providers:
  codex:
    auth_mode: host_state
    mount_host_state_in_api_mode: false
    commands:
      tui: 'bash -lc "echo stub-ok"'
      run_template: 'bash -lc "curl -s http://harness:8081/ >/dev/null 2>&1 || true; echo stub-ok"'
    auth:
      api_key:
        secrets_file: ~/.config/lasso/secrets/codex.env
        env_key: OPENAI_API_KEY
      host_state:
        paths:
          - ~/.codex/auth.json
    ownership:
      root_comm:
        - codex
  claude:
    auth_mode: host_state
    mount_host_state_in_api_mode: false
    commands:
      tui: 'bash -lc "echo stub-ok"'
      run_template: 'bash -lc "curl -s http://harness:8081/ >/dev/null 2>&1 || true; echo stub-ok"'
    auth:
      api_key:
        secrets_file: ~/.config/lasso/secrets/claude.env
        env_key: ANTHROPIC_API_KEY
      host_state:
        paths:
          - ~/.claude.json
    ownership:
      root_comm:
        - claude
CONFIG
}

lasso() {
  if [ -z "${CONFIG_PATH:-}" ]; then
    echo "ERROR: CONFIG_PATH is not set. Did you call setup_env?" >&2
    exit 1
  fi
  "$LASSO_BIN" --config "$CONFIG_PATH" "$@"
}

expect_fail() {
  set +e
  local output
  output=$("$@" 2>&1)
  local status=$?
  set -e
  if [ $status -eq 0 ]; then
    echo "ERROR: expected failure but command succeeded" >&2
    exit 1
  fi
  echo "$output"
}

json_field() {
  python3 -c 'import json,sys
path = sys.argv[1].split(".")
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    print("")
    raise SystemExit(0)
cur = data
for part in path:
    if cur is None:
        break
    if part.isdigit():
        cur = cur[int(part)] if isinstance(cur, list) and int(part) < len(cur) else None
    else:
        cur = cur.get(part) if isinstance(cur, dict) else None
if isinstance(cur, (dict, list)):
    print(json.dumps(cur))
elif cur is None:
    print("")
else:
    print(cur)
' "$1"
}

json_len() {
  python3 -c 'import json,sys
try:
    data=json.load(sys.stdin)
except json.JSONDecodeError:
    print(0)
    raise SystemExit(0)
if isinstance(data, list):
    print(len(data))
else:
    print(len(data) if data is not None else 0)
'
}

require_cmd "$LASSO_BIN"
