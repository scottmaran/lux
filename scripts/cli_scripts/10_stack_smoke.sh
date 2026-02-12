#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_common.sh"

require_cmd docker

setup_env
write_config "$LOG_ROOT" "$WORK_ROOT"

export HARNESS_RUN_CMD_TEMPLATE='curl -s https://example.com >/dev/null 2>&1 || true; echo stub-ok'

cleanup() {
  lasso down >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

lasso config apply
lasso up

status_json=""
count=0
for _ in $(seq 1 30); do
  status_json=$(lasso --json status)
  count=$(echo "$status_json" | json_field result | json_len)
  if [ "$count" -gt 0 ]; then
    break
  fi
  sleep 2
done
if [ "$count" -eq 0 ]; then
  echo "ERROR: expected running containers after up" >&2
  echo "$status_json" >&2
  exit 1
fi

if [ ! -f "$LOG_ROOT/audit.log" ]; then
  echo "ERROR: audit.log missing" >&2
  exit 1
fi
if [ ! -f "$LOG_ROOT/ebpf.jsonl" ]; then
  echo "ERROR: ebpf.jsonl missing" >&2
  exit 1
fi

run_output=$(lasso --json run "stub")
job_id=$(echo "$run_output" | json_field result.job_id)
if [ -z "$job_id" ]; then
  echo "ERROR: job_id not found in run output" >&2
  echo "$run_output" >&2
  exit 1
fi

job_dir="$LOG_ROOT/jobs/$job_id"
for _ in $(seq 1 30); do
  if [ -s "$job_dir/input.json" ] && [ -s "$job_dir/status.json" ] && [ -f "$job_dir/stderr.log" ]; then
    break
  fi
  sleep 1
done

status_state=""
status_exit_code=""
for _ in $(seq 1 30); do
  if [ -s "$job_dir/status.json" ]; then
    status_state=$(cat "$job_dir/status.json" | json_field status)
    status_exit_code=$(cat "$job_dir/status.json" | json_field exit_code)
    if [ "$status_state" = "complete" ] || [ "$status_state" = "failed" ]; then
      break
    fi
  fi
  sleep 1
done

if [ ! -s "$job_dir/input.json" ]; then
  echo "ERROR: job input.json missing" >&2
  exit 1
fi
if [ ! -s "$job_dir/status.json" ]; then
  echo "ERROR: job status.json missing" >&2
  exit 1
fi
if [ "$status_state" != "complete" ]; then
  echo "ERROR: expected complete job status, got: ${status_state:-<empty>}" >&2
  exit 1
fi
if [ "$status_exit_code" != "0" ]; then
  echo "ERROR: expected exit_code=0, got: ${status_exit_code:-<empty>}" >&2
  exit 1
fi
if [ ! -f "$job_dir/stdout.log" ]; then
  echo "ERROR: job stdout.log missing" >&2
  exit 1
fi

for _ in $(seq 1 20); do
  if [ -s "$LOG_ROOT/ebpf.jsonl" ]; then
    break
  fi
  sleep 1
done
if [ ! -s "$LOG_ROOT/ebpf.jsonl" ]; then
  echo "ERROR: ebpf.jsonl still empty after network activity" >&2
  exit 1
fi

run_output2=$(lasso --json run "stub")
job_id2=$(echo "$run_output2" | json_field result.job_id)
if [ -z "$job_id2" ] || [ "$job_id" = "$job_id2" ]; then
  echo "ERROR: expected distinct job IDs" >&2
  exit 1
fi

if ! command -v script >/dev/null 2>&1; then
  echo "ERROR: tui test requires script(1) to allocate a PTY." >&2
  exit 1
fi
if [ ! -t 0 ]; then
  echo "ERROR: tui test must be run from an interactive TTY." >&2
  exit 1
fi

script -q /dev/null "$LASSO_BIN" --config "$CONFIG_PATH" tui || {
  echo "ERROR: tui command failed" >&2
  exit 1
}
latest_session=$(ls -td "$LOG_ROOT"/sessions/session_* 2>/dev/null | head -n 1 || true)
if [ -z "$latest_session" ]; then
  echo "ERROR: no session directory created" >&2
  exit 1
fi
if [ ! -s "$latest_session/meta.json" ]; then
  echo "ERROR: session meta.json missing" >&2
  exit 1
fi
if ! grep -q "stub-ok" "$latest_session/stdout.log"; then
  echo "ERROR: session stdout missing expected output" >&2
  exit 1
fi

lasso down

status_json=$(lasso --json status)
count=$(echo "$status_json" | json_field result | json_len)
if [ "$count" -ne 0 ]; then
  echo "ERROR: expected no running containers after down" >&2
  echo "$status_json" >&2
  exit 1
fi

echo "ok"
