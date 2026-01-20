#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ROOT_DIR="${ROOT_DIR:-${REPO_ROOT}}"
WORKSPACE="${WORKSPACE:-${ROOT_DIR}/workspace}"
LOGS="${LOGS:-${ROOT_DIR}/logs}"
IMAGE="${IMAGE:-harness-collector:dev}"
COLLECTOR_NAME="${COLLECTOR_NAME:-harness-collector}"

echo "Using repo root: ${ROOT_DIR}"
echo "Workspace: ${WORKSPACE}"
echo "Logs: ${LOGS}"

mkdir -p "${WORKSPACE}" "${LOGS}"

if docker ps -a --format '{{.Names}}' | grep -q "^${COLLECTOR_NAME}\$"; then
  docker rm -f "${COLLECTOR_NAME}" >/dev/null 2>&1 || true
fi

docker build -t "${IMAGE}" "${REPO_ROOT}/collector"

docker run -d --name "${COLLECTOR_NAME}" \
  --pid=host --cgroupns=host --privileged \
  -e COLLECTOR_AUDIT_LOG=/logs/audit.log \
  -e COLLECTOR_EBPF_OUTPUT=/logs/ebpf.jsonl \
  -v "${LOGS}:/logs:rw" \
  -v "${WORKSPACE}:/work:ro" \
  -v /sys/fs/bpf:/sys/fs/bpf:rw \
  -v /sys/kernel/tracing:/sys/kernel/tracing:rw \
  -v /sys/kernel/debug:/sys/kernel/debug:rw \
  "${IMAGE}"

docker run --rm -v "${WORKSPACE}:/work" alpine sh -c \
  "echo hi > /work/a.txt; mv /work/a.txt /work/b.txt; chmod 600 /work/b.txt; rm /work/b.txt"

ROOT_DIR="${ROOT_DIR}" WORKSPACE="${WORKSPACE}" LOGS="${LOGS}" \
  "${SCRIPT_DIR}/ebpf_activity.sh"

docker stop "${COLLECTOR_NAME}" >/dev/null

echo "Audit log lines: $(wc -l < "${LOGS}/audit.log" 2>/dev/null || echo 0)"
echo "eBPF log lines: $(wc -l < "${LOGS}/ebpf.jsonl" 2>/dev/null || echo 0)"
echo "Tail audit log:"
tail -n 20 "${LOGS}/audit.log" 2>/dev/null || true
echo "Tail eBPF log:"
tail -n 20 "${LOGS}/ebpf.jsonl" 2>/dev/null || true
