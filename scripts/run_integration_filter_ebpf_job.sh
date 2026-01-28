#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export HARNESS_API_TOKEN="${HARNESS_API_TOKEN:-dev-token}"
export HARNESS_RUN_CMD_TEMPLATE="${HARNESS_RUN_CMD_TEMPLATE:-bash -lc {prompt}}"

LOGS="${ROOT_DIR}/logs"
mkdir -p "${LOGS}"
: > "${LOGS}/audit.log"
: > "${LOGS}/ebpf.jsonl"
: > "${LOGS}/filtered_ebpf.jsonl"
rm -rf "${LOGS}/jobs" "${LOGS}/sessions"

cat > "${LOGS}/ebpf_filtering_test.yaml" <<'YAML'
schema_version: ebpf.filtered.v1
input:
  audit_log: /logs/audit.log
  ebpf_log: /logs/ebpf.jsonl
sessions_dir: /logs/sessions
jobs_dir: /logs/jobs
output:
  jsonl: /logs/filtered_ebpf.jsonl
ownership:
  uid: 1001
  root_comm: []
include:
  event_types:
    - net_connect
    - net_send
    - dns_query
    - dns_response
    - unix_connect
exclude:
  comm: []
  unix_paths: []
  net_dst_ports: []
  net_dst_ips: []
linking:
  attach_cmd_to_net: true
  attach_cmd_strategy: last_exec_same_pid
YAML

compose=(docker compose -f compose.yml)

cleanup() {
  "${compose[@]}" down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${compose[@]}" up -d --build collector agent harness

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

export FILTER_PROMPT="curl -sI https://example.com >/dev/null"
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

"${compose[@]}" exec -T collector collector-ebpf-filter --config /logs/ebpf_filtering_test.yaml

python3 - <<'PY'
import json
from pathlib import Path

path = Path("logs/filtered_ebpf.jsonl")
rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
if not rows:
    raise SystemExit("Missing filtered eBPF rows.")
net_rows = [row for row in rows if row.get("event_type") in ("net_connect", "net_send")]
if not net_rows:
    raise SystemExit("Missing net_connect/net_send rows in filtered eBPF output.")
if any("job_id" not in row for row in net_rows):
    raise SystemExit("Filtered eBPF rows missing job_id.")
print(f"Filter eBPF job integration OK: {len(rows)} rows")
PY
