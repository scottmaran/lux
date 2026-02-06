#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required command: $1" >&2
    exit 1
  fi
}

require_cmd docker
require_cmd curl
require_cmd script
require_cmd python3

: "${HARNESS_API_TOKEN:=dev-token}"
: "${HARNESS_RUN_CMD_TEMPLATE:=bash -lc {prompt}}"
: "${LASSO_VERSION:=v0.1.4}"

TMP_DIR=$(mktemp -d)
LOG_ROOT="$TMP_DIR/logs"
WORK_ROOT="$TMP_DIR/workspace"
mkdir -p "$LOG_ROOT" "$WORK_ROOT"

export LASSO_LOG_ROOT="$LOG_ROOT"
export LASSO_WORKSPACE_ROOT="$WORK_ROOT"
export LASSO_VERSION
export HARNESS_API_TOKEN
export HARNESS_RUN_CMD_TEMPLATE
export COMPOSE_PROJECT_NAME="lasso-concurrent-test-$RANDOM"

compose=(docker compose -f compose.yml)

cleanup() {
  "${compose[@]}" down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${compose[@]}" up -d --build collector agent harness

# Wait for harness API to respond.
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
  echo "ERROR: harness API did not become ready on 127.0.0.1:8081." >&2
  exit 1
fi

# Wait for timeline file to exist (merge loop runs in collector).
for _ in $(seq 1 20); do
  if [ -f "$LOG_ROOT/filtered_timeline.jsonl" ]; then
    break
  fi
  sleep 1
done
if [ ! -f "$LOG_ROOT/filtered_timeline.jsonl" ]; then
  echo "ERROR: filtered_timeline.jsonl was not created." >&2
  exit 1
fi

TUI_ONE_MARK="TUI_ONE_${RANDOM}_$$"
TUI_TWO_MARK="TUI_TWO_${RANDOM}_$$"
TUI_ONE_PATH="/work/tui_one_${RANDOM}_$$.txt"
TUI_TWO_PATH="/work/tui_two_${RANDOM}_$$.txt"
JOB_ONE_PATH="/work/job_one_${RANDOM}_$$.txt"
JOB_TWO_PATH="/work/job_two_${RANDOM}_$$.txt"

TUI_SLEEP=4
JOB_SLEEP=4

TUI_ONE_CMD="bash -lc \"echo ${TUI_ONE_MARK}; sleep ${TUI_SLEEP}; printf one > ${TUI_ONE_PATH}\""
TUI_TWO_CMD="bash -lc \"echo ${TUI_TWO_MARK}; sleep ${TUI_SLEEP}; printf two > ${TUI_TWO_PATH}\""

script -q /dev/null "${compose[@]}" run --rm \
  -e HARNESS_MODE=tui \
  -e "HARNESS_TUI_CMD=${TUI_ONE_CMD}" \
  harness &
TUI_ONE_PID=$!

script -q /dev/null "${compose[@]}" run --rm \
  -e HARNESS_MODE=tui \
  -e "HARNESS_TUI_CMD=${TUI_TWO_CMD}" \
  harness &
TUI_TWO_PID=$!

JOB_ONE_PROMPT="sleep ${JOB_SLEEP}; printf one > ${JOB_ONE_PATH}"
JOB_TWO_PROMPT="sleep ${JOB_SLEEP}; printf two > ${JOB_TWO_PATH}"

start_job() {
  local prompt="$1"
  local response body http_code
  response="$(curl -sS -m 5 -w '\n%{http_code}' -X POST \
    -H "Content-Type: application/json" \
    -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
    -d "$(PROMPT="$prompt" python3 - <<'PY'
import json
import os
print(json.dumps({"prompt": os.environ["PROMPT"]}))
PY
)" \
    http://127.0.0.1:8081/run || true)"
  body="${response%$'\n'*}"
  http_code="${response##*$'\n'}"
  if [ -z "$body" ] || [ "$http_code" = "$response" ]; then
    echo "ERROR: empty /run response" >&2
    exit 1
  fi
  if [ "$http_code" != "202" ]; then
    echo "ERROR: unexpected /run status ${http_code}: ${body}" >&2
    exit 1
  fi
  printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
}

JOB_ONE_ID=$(start_job "$JOB_ONE_PROMPT")
JOB_TWO_ID=$(start_job "$JOB_TWO_PROMPT")

wait_job() {
  local job_id="$1"
  local status state
  for _ in $(seq 1 120); do
    status="$(curl -s -H "X-Harness-Token: ${HARNESS_API_TOKEN}" \
      "http://127.0.0.1:8081/jobs/${job_id}")"
    state="$(printf '%s' "$status" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
    if [ "$state" = "complete" ] || [ "$state" = "failed" ]; then
      if [ "$state" != "complete" ]; then
        echo "ERROR: job ${job_id} failed: ${status}" >&2
        exit 1
      fi
      return 0
    fi
    sleep 1
  done
  echo "ERROR: job ${job_id} did not complete in time" >&2
  exit 1
}

wait_job "$JOB_ONE_ID"
wait_job "$JOB_TWO_ID"

wait "$TUI_ONE_PID"
wait "$TUI_TWO_PID"

export LOG_ROOT
export TUI_ONE_MARK
export TUI_TWO_MARK
export TUI_ONE_PATH
export TUI_TWO_PATH
export JOB_ONE_PATH
export JOB_TWO_PATH
export JOB_ONE_ID
export JOB_TWO_ID

python3 - <<'PY'
import json
import os
import time
from pathlib import Path

log_root = Path(os.environ["LOG_ROOT"])
markers = {
    os.environ["TUI_ONE_MARK"]: os.environ["TUI_ONE_PATH"],
    os.environ["TUI_TWO_MARK"]: os.environ["TUI_TWO_PATH"],
}
job_paths = {
    os.environ["JOB_ONE_ID"]: os.environ["JOB_ONE_PATH"],
    os.environ["JOB_TWO_ID"]: os.environ["JOB_TWO_PATH"],
}

sessions_dir = log_root / "sessions"
timeline_path = log_root / "filtered_timeline.jsonl"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def find_session_ids():
    session_map = {}
    root_pids = {}
    if not sessions_dir.exists():
        return session_map, root_pids
    for entry in sessions_dir.iterdir():
        if not entry.is_dir():
            continue
        meta = read_json(entry / "meta.json") or {}
        session_id = meta.get("session_id") or entry.name
        stdout_path = entry / "stdout.log"
        try:
            stdout_text = stdout_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            stdout_text = ""
        for marker in markers:
            if marker in stdout_text:
                session_map[marker] = session_id
                root_pids[marker] = meta.get("root_pid")
    return session_map, root_pids


def job_root_pid(job_id: str):
    job_dir = log_root / "jobs" / job_id
    input_meta = read_json(job_dir / "input.json") or {}
    status_meta = read_json(job_dir / "status.json") or {}
    return input_meta.get("root_pid"), status_meta.get("root_pid")


def load_timeline():
    if not timeline_path.exists():
        return []
    rows = []
    for line in timeline_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def has_path_event(rows, *, session_id=None, job_id=None, path=None):
    for row in rows:
        if session_id is not None and row.get("session_id") != session_id:
            continue
        if job_id is not None and row.get("job_id") != job_id:
            continue
        if not (row.get("event_type") or "").startswith("fs_"):
            continue
        details = row.get("details") or {}
        if details.get("path") == path:
            return True
    return False


deadline = time.time() + 60
last_error = "unknown error"

while time.time() < deadline:
    session_map, session_root_pids = find_session_ids()
    missing_markers = [m for m in markers if m not in session_map]
    if missing_markers:
        last_error = f"missing session markers in stdout logs: {missing_markers}"
        time.sleep(2)
        continue

    missing_roots = [m for m, pid in session_root_pids.items() if not isinstance(pid, int)]
    if missing_roots:
        last_error = f"missing root_pid in session meta.json for markers: {missing_roots}"
        time.sleep(2)
        continue

    job_root_errors = []
    for job_id in job_paths:
        input_pid, status_pid = job_root_pid(job_id)
        if not isinstance(input_pid, int) or not isinstance(status_pid, int):
            job_root_errors.append(job_id)
    if job_root_errors:
        last_error = f"missing root_pid in job input/status for jobs: {job_root_errors}"
        time.sleep(2)
        continue

    rows = load_timeline()
    missing = []
    for marker, path in markers.items():
        session_id = session_map[marker]
        if not has_path_event(rows, session_id=session_id, path=path):
            missing.append(f"session {session_id} path {path}")
    for job_id, path in job_paths.items():
        if not has_path_event(rows, job_id=job_id, path=path):
            missing.append(f"job {job_id} path {path}")
    if missing:
        last_error = "timeline missing expected file events: " + ", ".join(missing)
        time.sleep(2)
        continue

    print("Concurrent session/job attribution OK")
    raise SystemExit(0)

raise SystemExit(last_error)
PY

echo "ok"
