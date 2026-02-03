#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export HARNESS_API_TOKEN="${HARNESS_API_TOKEN:-dev-token}"
export HARNESS_RUN_CMD_TEMPLATE="${HARNESS_RUN_CMD_TEMPLATE:-echo stub-ok}"

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

response="$(curl -sS -m 5 -w '\n%{http_code}' -X POST \
  -H "Content-Type: application/json" \
  -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
  -d '{"prompt":"stub-run"}' \
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
for _ in $(seq 1 60); do
  status="$(curl -s -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
    "http://127.0.0.1:8081/jobs/${job_id}")"
  state="$(printf '%s' "$status" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  if [ "$state" = "complete" ] || [ "$state" = "failed" ]; then
    break
  fi
  sleep 1
done

if [ "$state" != "complete" ]; then
  echo "Job did not complete successfully: ${status}" >&2
  exit 1
fi

stdout_path="$(printf '%s' "$status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("output_path", ""))')"

if [ -z "$stdout_path" ]; then
  echo "Missing stdout path in status: ${status}" >&2
  exit 1
fi

if [[ "$stdout_path" == /logs/* ]]; then
  host_stdout_path="${ROOT_DIR}/logs/${stdout_path#/logs/}"
else
  echo "Unexpected stdout path (not /logs/*): ${stdout_path}" >&2
  exit 1
fi

if [ ! -f "$host_stdout_path" ]; then
  echo "Missing stdout log at ${host_stdout_path}" >&2
  exit 1
fi

if ! grep -q "stub-ok" "$host_stdout_path"; then
  echo "Expected stub output not found in ${host_stdout_path}" >&2
  exit 1
fi

echo "Stub integration OK: ${host_stdout_path}"
