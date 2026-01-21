#!/usr/bin/env bash
set -euo pipefail

SSH_DIR="/home/agent/.ssh"
AUTHORIZED_KEYS_FILE="${SSH_DIR}/authorized_keys"
AUTH_WAIT_SEC="${AGENT_AUTH_WAIT_SEC:-30}"

if [[ ! -f /config/authorized_keys && ! -f /run/authorized_keys ]]; then
  for _ in $(seq 1 "${AUTH_WAIT_SEC}"); do
    sleep 1
    if [[ -f /config/authorized_keys || -f /run/authorized_keys ]]; then
      break
    fi
  done
fi

if [[ -f /config/authorized_keys ]]; then
  cp /config/authorized_keys "${AUTHORIZED_KEYS_FILE}"
elif [[ -f /run/authorized_keys ]]; then
  cp /run/authorized_keys "${AUTHORIZED_KEYS_FILE}"
fi

if [[ ! -f "${AUTHORIZED_KEYS_FILE}" ]]; then
  echo "WARNING: no authorized keys provided; SSH logins will fail." >&2
  touch "${AUTHORIZED_KEYS_FILE}"
fi

chown -R agent:agent "${SSH_DIR}"
chmod 700 "${SSH_DIR}"
chmod 600 "${AUTHORIZED_KEYS_FILE}"

ssh-keygen -A >/dev/null 2>&1

if ! command -v codex >/dev/null 2>&1; then
  echo "WARNING: codex CLI not found in PATH." >&2
fi

# replaces the entrypoint shell with sshd (so it becomes PID 1), 
# runs it in foreground (-D), and sends logs to stderr (-e) so Docker captures them. 
# Keeps the container alive and makes SSH logs visible in container logs.
exec /usr/sbin/sshd -D -e
