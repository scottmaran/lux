#!/bin/sh
set -e

AUDIT_LOG=${COLLECTOR_AUDIT_OUTPUT:-${COLLECTOR_AUDIT_LOG:-/logs/audit.log}}
EBPF_LOG=${COLLECTOR_EBPF_OUTPUT:-/logs/ebpf.jsonl}

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

auditd
AUDITD_PID=$(pidof auditd || true)
if ! /usr/sbin/auditctl -D; then
  echo "collector: warning: failed to clear audit rules" >&2
fi
if ! /usr/sbin/auditctl -R /etc/audit/rules.d/harness.rules; then
  echo "collector: warning: failed to load audit rules" >&2
fi

tail -F "${AUDIT_LOG}" &
TAIL_PID=$!

trap 'kill ${TAIL_PID} 2>/dev/null || true; kill ${AUDITD_PID} 2>/dev/null || true' TERM INT
wait "${TAIL_PID}"
