#!/usr/bin/env bash
set -euo pipefail

ACCESS_LOG="${PROXY_ACCESS_LOG:-/logs/squid_access.log}"
JSON_LOG="${PROXY_JSON_LOG:-/logs/filtered_proxy.jsonl}"
CONF_FILE="${PROXY_CONF_FILE:-/etc/squid/squid.conf}"

mkdir -p /logs

# Ensure logs exist and are writable for squid.
if id proxy >/dev/null 2>&1; then
  chown -R proxy:proxy /logs || true
fi

touch "${ACCESS_LOG}" "${JSON_LOG}" || true

# Start squid in the foreground.
squid -N -f "${CONF_FILE}" &
SQUID_PID=$!

# Stream squid access logs into JSONL.
tail -n 0 -F "${ACCESS_LOG}" | /usr/local/bin/parse_squid_access.py --output "${JSON_LOG}" &
PARSER_PID=$!

trap 'kill ${PARSER_PID} 2>/dev/null || true; kill ${SQUID_PID} 2>/dev/null || true' TERM INT
wait "${SQUID_PID}"
