#!/bin/sh
set -e

AUDIT_LOG=${COLLECTOR_AUDIT_OUTPUT:-${COLLECTOR_AUDIT_LOG:-/logs/audit.log}}
EBPF_LOG=${COLLECTOR_EBPF_OUTPUT:-/logs/ebpf.jsonl}
EBPF_BIN=${COLLECTOR_EBPF_BIN:-/usr/local/bin/collector-ebpf-loader}
EBPF_OBJ=${COLLECTOR_EBPF_BPF:-/usr/local/share/collector/collector-ebpf.o}
FILTER_CONFIG=${COLLECTOR_FILTER_CONFIG:-/etc/collector/filtering.yaml}
FILTER_LOG=${COLLECTOR_FILTER_OUTPUT:-/logs/filtered_audit.jsonl}
FILTER_BIN=${COLLECTOR_FILTER_BIN:-/usr/local/bin/collector-audit-filter}
EBPF_FILTER_CONFIG=${COLLECTOR_EBPF_FILTER_CONFIG:-/etc/collector/ebpf_filtering.yaml}
EBPF_FILTER_LOG=${COLLECTOR_EBPF_FILTER_OUTPUT:-/logs/filtered_ebpf.jsonl}
EBPF_FILTER_BIN=${COLLECTOR_EBPF_FILTER_BIN:-/usr/local/bin/collector-ebpf-filter}
EBPF_FILTER_POLL=${COLLECTOR_EBPF_FILTER_POLL:-0.5}
MERGE_FILTER_CONFIG=${COLLECTOR_MERGE_FILTER_CONFIG:-/etc/collector/merge_filtering.yaml}
MERGE_FILTER_LOG=${COLLECTOR_MERGE_FILTER_OUTPUT:-/logs/filtered_timeline.jsonl}
MERGE_FILTER_BIN=${COLLECTOR_MERGE_FILTER_BIN:-/usr/local/bin/collector-merge-filtered}
MERGE_FILTER_INTERVAL=${COLLECTOR_MERGE_FILTER_INTERVAL:-2}

mkdir -p /logs /sys/kernel/tracing /sys/kernel/debug /sys/fs/bpf

if command -v mountpoint >/dev/null 2>&1; then
  if ! mountpoint -q /sys/kernel/tracing; then
    mount -t tracefs tracefs /sys/kernel/tracing 2>/dev/null || true
  fi
  if ! mountpoint -q /sys/kernel/debug; then
    mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true
  fi
fi

if [ -f /etc/audit/auditd.conf ]; then
  sed -i "s#^log_file = .*#log_file = ${AUDIT_LOG}#" /etc/audit/auditd.conf
fi

touch "${AUDIT_LOG}" 2>/dev/null || true
chown root:adm "${AUDIT_LOG}" 2>/dev/null || chown root:root "${AUDIT_LOG}" 2>/dev/null || true
chmod 0640 "${AUDIT_LOG}" 2>/dev/null || true

touch "${EBPF_LOG}" 2>/dev/null || true
chown root:adm "${EBPF_LOG}" 2>/dev/null || chown root:root "${EBPF_LOG}" 2>/dev/null || true
chmod 0640 "${EBPF_LOG}" 2>/dev/null || true

touch "${FILTER_LOG}" 2>/dev/null || true
chown root:adm "${FILTER_LOG}" 2>/dev/null || chown root:root "${FILTER_LOG}" 2>/dev/null || true
chmod 0640 "${FILTER_LOG}" 2>/dev/null || true

touch "${EBPF_FILTER_LOG}" 2>/dev/null || true
chown root:adm "${EBPF_FILTER_LOG}" 2>/dev/null || chown root:root "${EBPF_FILTER_LOG}" 2>/dev/null || true
chmod 0640 "${EBPF_FILTER_LOG}" 2>/dev/null || true

touch "${MERGE_FILTER_LOG}" 2>/dev/null || true
chown root:adm "${MERGE_FILTER_LOG}" 2>/dev/null || chown root:root "${MERGE_FILTER_LOG}" 2>/dev/null || true
chmod 0640 "${MERGE_FILTER_LOG}" 2>/dev/null || true

auditd
AUDITD_PID=$(pidof auditd 2>/dev/null || cat /var/run/auditd.pid 2>/dev/null || true)
if ! /usr/sbin/auditctl -D; then
  echo "collector: warning: failed to clear audit rules" >&2
fi
if ! /usr/sbin/auditctl -R /etc/audit/rules.d/harness.rules; then
  echo "collector: warning: failed to load audit rules" >&2
fi

/usr/bin/env COLLECTOR_FILTER_CONFIG="${FILTER_CONFIG}" \
  COLLECTOR_AUDIT_LOG="${AUDIT_LOG}" \
  COLLECTOR_FILTER_OUTPUT="${FILTER_LOG}" \
  "${FILTER_BIN}" --config "${FILTER_CONFIG}" --follow &
FILTER_PID=$!

/usr/bin/env COLLECTOR_EBPF_FILTER_CONFIG="${EBPF_FILTER_CONFIG}" \
  COLLECTOR_AUDIT_LOG="${AUDIT_LOG}" \
  COLLECTOR_EBPF_LOG="${EBPF_LOG}" \
  COLLECTOR_EBPF_FILTER_OUTPUT="${EBPF_FILTER_LOG}" \
  "${EBPF_FILTER_BIN}" --config "${EBPF_FILTER_CONFIG}" --follow \
  --poll-interval "${EBPF_FILTER_POLL}" &
EBPF_FILTER_PID=$!

/usr/bin/env COLLECTOR_EBPF_OUTPUT="${EBPF_LOG}" COLLECTOR_EBPF_BPF="${EBPF_OBJ}" "${EBPF_BIN}" &
EBPF_PID=$!

if [ -f "${MERGE_FILTER_CONFIG}" ]; then
  (
    while true; do
      /usr/bin/env COLLECTOR_MERGE_CONFIG="${MERGE_FILTER_CONFIG}" \
        "${MERGE_FILTER_BIN}" --config "${MERGE_FILTER_CONFIG}" >/dev/null 2>&1 || true
      sleep "${MERGE_FILTER_INTERVAL}"
    done
  ) &
  MERGE_PID=$!
else
  echo "collector: warning: missing merge filter config at ${MERGE_FILTER_CONFIG}" >&2
fi

tail -F "${AUDIT_LOG}" &
TAIL_PID=$!

trap 'kill ${TAIL_PID} 2>/dev/null || true; kill ${FILTER_PID} 2>/dev/null || true; kill ${EBPF_FILTER_PID} 2>/dev/null || true; kill ${MERGE_PID} 2>/dev/null || true; kill ${EBPF_PID} 2>/dev/null || true; kill ${AUDITD_PID} 2>/dev/null || true' TERM INT
wait "${EBPF_PID}"
