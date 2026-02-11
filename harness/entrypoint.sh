#!/usr/bin/env bash
set -euo pipefail

KEY_DIR="${HARNESS_KEYS_DIR:-/harness/keys}"
SSH_KEY_PATH="${HARNESS_SSH_KEY_PATH:-${KEY_DIR}/ssh_key}"
AUTHORIZED_KEYS_PATH="${HARNESS_AUTHORIZED_KEYS_PATH:-${KEY_DIR}/authorized_keys}"
MODE="${HARNESS_MODE:-}"

mkdir -p "${KEY_DIR}"

if [[ ! -w "${KEY_DIR}" ]]; then
  echo "ERROR: ${KEY_DIR} is not writable. Ensure the shared key volume permits uid 1002 writes." >&2
  exit 1
fi

if [[ ! -f "${SSH_KEY_PATH}" || ! -f "${SSH_KEY_PATH}.pub" ]]; then
  umask 077
  ssh-keygen -t ed25519 -N "" -f "${SSH_KEY_PATH}" >/dev/null
fi

if [[ ! -f "${AUTHORIZED_KEYS_PATH}" ]]; then
  cp "${SSH_KEY_PATH}.pub" "${AUTHORIZED_KEYS_PATH}"
fi

chmod 600 "${SSH_KEY_PATH}" "${SSH_KEY_PATH}.pub" "${AUTHORIZED_KEYS_PATH}"

export HARNESS_SSH_KEY_PATH="${SSH_KEY_PATH}"
export HARNESS_AUTHORIZED_KEYS_PATH="${AUTHORIZED_KEYS_PATH}"

if [[ ! -w "/logs" ]]; then
  echo "ERROR: /logs is not writable. Ensure the host logs directory is writable by uid 1002." >&2
  exit 1
fi

if [[ -z "${MODE}" ]]; then
  if [[ -t 0 ]]; then
    MODE="tui"
  else
    MODE="server"
  fi
fi

exec python3 /usr/local/bin/harness.py "${MODE}"
