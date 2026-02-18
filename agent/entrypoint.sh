#!/usr/bin/env bash
set -euo pipefail

SSH_DIR="/home/agent/.ssh"
AUTHORIZED_KEYS_FILE="${SSH_DIR}/authorized_keys"
AUTH_WAIT_SEC="${AGENT_AUTH_WAIT_SEC:-30}"

CODEX_DIR="/home/agent/.codex"
CODEX_AUTH_SRC="/run/codex_auth.json"
CODEX_SKILLS_SRC="/run/codex_skills"

PROFILE_EXPORT_FILE="/etc/profile.d/lux-provider-auth.sh"

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

bool_true() {
  local value="${1:-}"
  case "${value,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

copy_host_state_item() {
  local src="$1"
  local dst="$2"
  if [[ -z "${src}" || -z "${dst}" ]]; then
    return
  fi
  if [[ ! -e "${src}" ]]; then
    echo "WARNING: provider host-state mount missing at ${src}" >&2
    return
  fi

  mkdir -p "$(dirname "${dst}")"
  if [[ -d "${src}" ]]; then
    rm -rf "${dst}"
    cp -a "${src}" "${dst}"
    chown -R agent:agent "${dst}"
    chmod -R u+rwX,go-rwx "${dst}" || true
    return
  fi

  cp "${src}" "${dst}"
  chown agent:agent "${dst}"
  chmod 600 "${dst}"
}

copy_provider_host_state_from_env() {
  local count="${LUX_PROVIDER_HOST_STATE_COUNT:-0}"
  if ! [[ "${count}" =~ ^[0-9]+$ ]]; then
    echo "WARNING: invalid LUX_PROVIDER_HOST_STATE_COUNT=${count}; skipping host-state copy." >&2
    return
  fi
  if [[ "${count}" -eq 0 ]]; then
    return
  fi

  local idx=0
  while [[ "${idx}" -lt "${count}" ]]; do
    local src_var="LUX_PROVIDER_HOST_STATE_SRC_${idx}"
    local dst_var="LUX_PROVIDER_HOST_STATE_DST_${idx}"
    local src="${!src_var:-}"
    local dst="${!dst_var:-}"
    copy_host_state_item "${src}" "${dst}"
    idx=$((idx + 1))
  done
}

write_provider_env_export() {
  local key="$1"
  local value="$2"
  mkdir -p /etc/profile.d
  printf 'export %s=%q\n' "${key}" "${value}" > "${PROFILE_EXPORT_FILE}"
  chown root:root "${PROFILE_EXPORT_FILE}"
  chmod 600 "${PROFILE_EXPORT_FILE}"
}

load_api_key_auth_from_secrets_file() {
  local secrets_file="$1"
  local env_key="$2"
  if [[ -z "${secrets_file}" || -z "${env_key}" ]]; then
    echo "ERROR: API-key auth requires LUX_PROVIDER_SECRETS_FILE and LUX_PROVIDER_ENV_KEY." >&2
    exit 1
  fi
  if [[ ! -r "${secrets_file}" ]]; then
    echo "ERROR: cannot read secrets file: ${secrets_file}" >&2
    exit 1
  fi

  set -a
  # shellcheck source=/dev/null
  source "${secrets_file}"
  set +a

  local key_value="${!env_key:-}"
  if [[ -z "${key_value}" ]]; then
    echo "ERROR: required API key ${env_key} was not found in ${secrets_file}" >&2
    exit 1
  fi

  export "${env_key}=${key_value}"
  write_provider_env_export "${env_key}" "${key_value}"
}

bootstrap_provider_auth() {
  local provider="${LUX_PROVIDER:-}"
  local auth_mode="${LUX_AUTH_MODE:-}"
  local mount_host_state="${LUX_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE:-false}"
  local env_key="${LUX_PROVIDER_ENV_KEY:-}"
  local secrets_file="${LUX_PROVIDER_SECRETS_FILE:-}"

  rm -f "${PROFILE_EXPORT_FILE}" || true
  if [[ -z "${provider}" || -z "${auth_mode}" ]]; then
    return
  fi

  case "${auth_mode}" in
    api_key)
      load_api_key_auth_from_secrets_file "${secrets_file}" "${env_key}"
      if bool_true "${mount_host_state}"; then
        copy_provider_host_state_from_env
      fi
      ;;
    host_state)
      copy_provider_host_state_from_env
      ;;
    *)
      echo "ERROR: unsupported auth mode '${auth_mode}' for provider '${provider}'." >&2
      exit 1
      ;;
  esac
}

import_legacy_codex_mounts() {
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

bootstrap_provider_auth
import_legacy_codex_mounts

ssh-keygen -A >/dev/null 2>&1

(
  while true; do
    sync_authorized_keys
    sleep 2
  done
) &

if ! command -v codex >/dev/null 2>&1; then
  echo "WARNING: codex CLI not found in PATH." >&2
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "WARNING: claude CLI not found in PATH." >&2
fi

exec /usr/sbin/sshd -D -e
