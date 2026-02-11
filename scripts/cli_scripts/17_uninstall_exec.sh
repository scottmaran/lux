#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

require_cmd docker

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

cleanup() {
  docker compose --env-file "$ENV_FILE" -p "$LASSO_PROJECT_NAME" -f "$LASSO_BUNDLE_DIR/compose.yml" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

lasso config apply
lasso up --wait --timeout-sec "${LASSO_WAIT_TIMEOUT_SEC:-120}"

INSTALL_DIR="$TMP_DIR/install"
BIN_DIR="$TMP_DIR/bin"
VERSION_DIR="$INSTALL_DIR/versions/0.1.0"
CURRENT_LINK="$INSTALL_DIR/current"
BIN_LINK="$BIN_DIR/lasso"

mkdir -p "$VERSION_DIR" "$BIN_DIR"
touch "$VERSION_DIR/lasso"
ln -sfn "$VERSION_DIR" "$CURRENT_LINK"
ln -sfn "$CURRENT_LINK/lasso" "$BIN_LINK"

LASSO_INSTALL_DIR="$INSTALL_DIR" LASSO_BIN_DIR="$BIN_DIR" \
  lasso --json uninstall --yes --remove-config --remove-data --all-versions

if [ -e "$BIN_LINK" ] || [ -e "$CURRENT_LINK" ]; then
  echo "ERROR: expected CLI links to be removed by uninstall" >&2
  exit 1
fi
if [ -e "$INSTALL_DIR/versions" ]; then
  echo "ERROR: expected versions directory to be removed by uninstall --all-versions" >&2
  exit 1
fi
if [ -e "$CONFIG_PATH" ] || [ -e "$ENV_FILE" ]; then
  echo "ERROR: expected config files to be removed by uninstall --remove-config" >&2
  exit 1
fi
if [ -e "$LOG_ROOT" ] || [ -e "$WORK_ROOT" ]; then
  echo "ERROR: expected data directories to be removed by uninstall --remove-data" >&2
  exit 1
fi

if docker ps --filter "label=com.docker.compose.project=$LASSO_PROJECT_NAME" --format '{{.ID}}' | grep -q .; then
  echo "ERROR: expected no running containers after uninstall down step" >&2
  exit 1
fi

echo "ok"
