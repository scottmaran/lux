#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export HARNESS_API_TOKEN="${HARNESS_API_TOKEN:-dev-token}"
export HARNESS_RUN_CMD_TEMPLATE="${HARNESS_RUN_CMD_TEMPLATE:-bash -lc {prompt}}"
export FILTER_PATH="/work/temp_${RANDOM}_$$.txt"

LOGS="${ROOT_DIR}/logs"
mkdir -p "${LOGS}"
: > "${LOGS}/filtered_audit.jsonl"
: > "${LOGS}/audit.log"
rm -rf "${LOGS}/jobs" "${LOGS}/sessions"
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

"${compose[@]}" up -d --build collector agent proxy harness

code=""
for _ in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w "%{http_code}" -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
    http://127.0.0.1:8081/jobs/_ || true)"
  if [ "$code" = "404" ]; then
    break
  fi
  sleep 1
done

if [ "$code" != "404" ]; then
  echo "Harness API did not become ready on 127.0.0.1:8081." >&2
  exit 1
fi

export FILTER_PROMPT="pwd; printf 'hello world' > ${FILTER_PATH}"
payload="$(python3 - <<'PY'
import json
import os
print(json.dumps({"prompt": os.environ["FILTER_PROMPT"]}))
PY
)"

response="$(curl -sS -m 5 -w '\n%{http_code}' -X POST \
  -H "Content-Type: application/json" \
  -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
  -d "${payload}" \
  http://127.0.0.1:8081/run || true)"
body="${response%$'\n'*}"
http_code="${response##*$'\n'}"

if [ -z "$body" ] || [ "$http_code" = "$response" ]; then
  echo "Empty /run response (curl failed?): ${response}" >&2
  exit 1
fi

if [ "$http_code" != "202" ]; then
  echo "Unexpected /run status ${http_code}: ${body}" >&2
  exit 1
fi

job_id="$(printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"

status=""
state=""
for _ in $(seq 1 180); do
  status="$(curl -s -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
    "http://127.0.0.1:8081/jobs/${job_id}")"
  state="$(printf '%s' "$status" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  if [ "$state" = "complete" ] || [ "$state" = "failed" ]; then
    break
  fi
  sleep 1
done

if [ "$state" != "complete" ]; then
  echo "Codex job did not complete successfully: ${status}" >&2
  exit 1
fi

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
if any("job_id" not in row for row in fs_rows):
    raise SystemExit("fs_create rows missing job_id.")
exec_rows = [row for row in rows if row.get("event_type") == "exec"]
if not exec_rows:
    raise SystemExit("Missing exec rows in filtered output.")
print(f"Filter job integration OK: {len(rows)} rows")
PY
