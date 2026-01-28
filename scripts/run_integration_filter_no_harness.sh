#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOGS="${ROOT_DIR}/logs"
mkdir -p "${LOGS}"
: > "${LOGS}/filtered_audit.jsonl"
: > "${LOGS}/audit.log"

compose=(docker compose -f compose.yml)

cleanup() {
  "${compose[@]}" down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${compose[@]}" up -d --build collector agent

sleep 3
"${compose[@]}" exec -T collector collector-audit-filter --config /etc/collector/filtering.yaml

lines="$(wc -l < "${LOGS}/filtered_audit.jsonl" 2>/dev/null || echo 0)"
if [ "${lines}" -ne 0 ]; then
  echo "Expected 0 filtered rows, found ${lines}." >&2
  exit 1
fi

echo "Filter no-harness integration OK: ${lines} rows"
