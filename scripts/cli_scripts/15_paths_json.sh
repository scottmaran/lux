#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

cleanup() {
  rm -rf "${TMP_DIR:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

lasso config apply

INSTALL_DIR="$TMP_DIR/install"
BIN_DIR="$TMP_DIR/bin"
paths_json=$(LASSO_INSTALL_DIR="$INSTALL_DIR" LASSO_BIN_DIR="$BIN_DIR" lasso --json paths)

config_path=$(echo "$paths_json" | json_field result.config_path)
env_file=$(echo "$paths_json" | json_field result.env_file)
bundle_dir=$(echo "$paths_json" | json_field result.bundle_dir)
log_root=$(echo "$paths_json" | json_field result.log_root)
workspace_root=$(echo "$paths_json" | json_field result.workspace_root)
install_dir=$(echo "$paths_json" | json_field result.install_dir)
bin_dir=$(echo "$paths_json" | json_field result.bin_dir)

if [ "$config_path" != "$CONFIG_PATH" ]; then
  echo "ERROR: config_path mismatch: $config_path" >&2
  exit 1
fi
if [ "$env_file" != "$ENV_FILE" ]; then
  echo "ERROR: env_file mismatch: $env_file" >&2
  exit 1
fi
if [ "$bundle_dir" != "$LASSO_BUNDLE_DIR" ]; then
  echo "ERROR: bundle_dir mismatch: $bundle_dir" >&2
  exit 1
fi
if [ "$log_root" != "$LOG_ROOT" ]; then
  echo "ERROR: log_root mismatch: $log_root" >&2
  exit 1
fi
if [ "$workspace_root" != "$WORK_ROOT" ]; then
  echo "ERROR: workspace_root mismatch: $workspace_root" >&2
  exit 1
fi
if [ "$install_dir" != "$INSTALL_DIR" ]; then
  echo "ERROR: install_dir mismatch: $install_dir" >&2
  exit 1
fi
if [ "$bin_dir" != "$BIN_DIR" ]; then
  echo "ERROR: bin_dir mismatch: $bin_dir" >&2
  exit 1
fi

echo "ok"
