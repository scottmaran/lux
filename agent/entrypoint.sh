#!/usr/bin/env bash
set -euo pipefail

SSH_DIR="/home/agent/.ssh"
AUTHORIZED_KEYS_FILE="${SSH_DIR}/authorized_keys"
AUTH_WAIT_SEC="${AGENT_AUTH_WAIT_SEC:-30}"
CODEX_DIR="/home/agent/.codex"
CODEX_AUTH_SRC="/run/codex_auth.json"
CODEX_SKILLS_SRC="/run/codex_skills"

sync_authorized_keys() {
  local src=""
  if [[ -f /config/authorized_keys ]]; then
    src="/config/authorized_keys"
  elif [[ -f /run/authorized_keys ]]; then
    src="/run/authorized_keys"
  fi

  if [[ -n "${src}" ]]; then
    cp "${src}" "${AUTHORIZED_KEYS_FILE}"
    chown agent:agent "${AUTHORIZED_KEYS_FILE}"
    chmod 600 "${AUTHORIZED_KEYS_FILE}"
  fi
}

if [[ ! -f /config/authorized_keys && ! -f /run/authorized_keys ]]; then
  for _ in $(seq 1 "${AUTH_WAIT_SEC}"); do
    sleep 1
    if [[ -f /config/authorized_keys || -f /run/authorized_keys ]]; then
      break
    fi
  done
fi

sync_authorized_keys

if [[ ! -f "${AUTHORIZED_KEYS_FILE}" ]]; then
  echo "WARNING: no authorized keys provided; SSH logins will fail." >&2
  touch "${AUTHORIZED_KEYS_FILE}"
fi

chown -R agent:agent "${SSH_DIR}"
chmod 700 "${SSH_DIR}"
if [[ -f "${AUTHORIZED_KEYS_FILE}" ]]; then
  chmod 600 "${AUTHORIZED_KEYS_FILE}"
fi

if [[ -f "${CODEX_AUTH_SRC}" ]]; then
  mkdir -p "${CODEX_DIR}"
  cp "${CODEX_AUTH_SRC}" "${CODEX_DIR}/auth.json"
  chown -R agent:agent "${CODEX_DIR}"
  chmod 700 "${CODEX_DIR}"
  chmod 600 "${CODEX_DIR}/auth.json"
fi

if [[ -d "${CODEX_SKILLS_SRC}" ]]; then
  mkdir -p "${CODEX_DIR}"
  rm -rf "${CODEX_DIR}/skills"
  cp -a "${CODEX_SKILLS_SRC}" "${CODEX_DIR}/skills"
  chown -R agent:agent "${CODEX_DIR}/skills"
  chmod -R u+rwX,go+rX "${CODEX_DIR}/skills"
fi

ssh-keygen -A >/dev/null 2>&1

# keep ssh authorized_keys synced in case harness writes after agent startup
(
  while true; do
    sync_authorized_keys
    sleep 2
  done
) &

if ! command -v codex >/dev/null 2>&1; then
  echo "WARNING: codex CLI not found in PATH." >&2
fi

# replaces the entrypoint shell with sshd (so it becomes PID 1), 
# runs it in foreground (-D), and sends logs to stderr (-e) so Docker captures them. 
# Keeps the container alive and makes SSH logs visible in container logs.
exec /usr/sbin/sshd -D -e
