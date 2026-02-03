#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v script >/dev/null 2>&1; then
  echo "Missing 'script' command (required to allocate a TTY for TUI mode)." >&2
  exit 1
fi

LOGS="${ROOT_DIR}/logs"
mkdir -p "${LOGS}"
: > "${LOGS}/filtered_audit.jsonl"
: > "${LOGS}/audit.log"
rm -rf "${LOGS}/jobs" "${LOGS}/sessions"
export FILTER_PATH="/work/temp_${RANDOM}_$$.txt"
cat > "${LOGS}/filtering_test.yaml" <<'YAML'
schema_version: auditd.filtered.v1
input:
  audit_log: /logs/audit.log
sessions_dir: /logs/sessions
jobs_dir: /logs/jobs
output:
  jsonl: /logs/filtered_audit.jsonl
grouping:
  strategy: audit_seq
agent_ownership:
  uid: 1001
  root_comm: []
exec:
  include_keys:
    - exec
  shell_comm:
    - bash
    - sh
  shell_cmd_flag: "-lc"
  helper_exclude_comm: []
  helper_exclude_argv_prefix: []
fs:
  include_keys:
    - fs_watch
    - fs_change
    - fs_meta
  include_paths_prefix:
    - /work/
linking:
  attach_cmd_to_fs: true
  attach_cmd_strategy: last_exec_same_pid
YAML

compose=(docker compose -f compose.yml)

cleanup() {
  "${compose[@]}" down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${compose[@]}" up -d --build collector agent proxy

TUI_CMD="bash -lc \"pwd; printf 'hello world' > ${FILTER_PATH}\""

script -q /dev/null "${compose[@]}" run --rm --service-ports \
  -e HARNESS_MODE=tui \
  -e "HARNESS_TUI_CMD=${TUI_CMD}" \
  harness

sleep 3
"${compose[@]}" exec -T collector collector-audit-filter --config /logs/filtering_test.yaml

python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path("logs/filtered_audit.jsonl")
rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
expected_path = os.environ["FILTER_PATH"]
fs_rows = [row for row in rows if row.get("event_type") == "fs_create" and row.get("path") == expected_path]
if not fs_rows:
    raise SystemExit(f"Missing fs_create for {expected_path} in filtered output.")
if any(row.get("session_id") == "unknown" for row in fs_rows):
    raise SystemExit("fs_create rows missing session_id mapping.")
if any("job_id" in row for row in fs_rows):
    raise SystemExit("fs_create rows should not carry job_id in TUI mode.")
print(f"Filter TUI integration OK: {len(rows)} rows")
PY
