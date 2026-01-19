#!/bin/sh
set -e

AUDIT_LOG=${COLLECTOR_AUDIT_OUTPUT:-${COLLECTOR_AUDIT_LOG:-/logs/audit.log}}
EBPF_LOG=${COLLECTOR_EBPF_OUTPUT:-/logs/ebpf.jsonl}
TRACEE_EVENTS=${TRACEE_EVENTS:-net_packet_dns_request,net_packet_dns_response}
TRACEE_EXTRA_ARGS=${TRACEE_EXTRA_ARGS:-}
LIBBPFGO_OSRELEASE_FILE=${LIBBPFGO_OSRELEASE_FILE:-/etc/os-release}

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

auditd
if command -v augenrules >/dev/null 2>&1; then
  augenrules --load
else
  auditctl -D
  auditctl -R /etc/audit/rules.d/harness.rules
fi

export LIBBPFGO_OSRELEASE_FILE
exec tracee --output "json:${EBPF_LOG}" --events "${TRACEE_EVENTS}" ${TRACEE_EXTRA_ARGS}
