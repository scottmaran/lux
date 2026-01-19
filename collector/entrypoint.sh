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

auditd -f &
AUDITD_PID=$!
if ! /usr/sbin/auditctl -D; then
  echo "collector: warning: failed to clear audit rules" >&2
fi
if ! /usr/sbin/auditctl -R /etc/audit/rules.d/harness.rules; then
  echo "collector: warning: failed to load audit rules" >&2
fi

trap 'kill ${AUDITD_PID} 2>/dev/null || true' TERM INT
wait "${AUDITD_PID}"
