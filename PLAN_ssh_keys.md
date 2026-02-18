# SSH Host Key Stability + Harness Verification Plan

Status: draft
Owner: codex
Created: 2026-02-18
Last updated: 2026-02-18

## Problem Summary

- We observed intermittent `lux tui --provider codex` failures with:
  `Error: The cursor position could not be read within a normal duration`.
- Session logs for the failing run also show:
  `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`
- Root cause: `harness` persists `known_hosts` in `harness_keys`, while `agent`
  host keys can change on container recreation (`ssh-keygen -A` at startup).
- Current harness SSH setting is `StrictHostKeyChecking=no`, which does not
  enforce stable trust and still allows noisy mismatch output in the PTY stream.

## Goals

1. Keep agent SSH host keys stable across restarts/recreates.
2. Switch harness host-key policy to `StrictHostKeyChecking=accept-new`.
3. Provide a clear migration path for existing stale `known_hosts` entries.
4. Keep implementation minimal and localized.

## Non-Goals

- No changes to provider auth modes or run attribution logic.
- No SSH CA/certificate infrastructure.
- No runtime control-plane behavior changes.

## Proposed Implementation

### 1) Persist Agent SSH Host Keys

Files:
- `compose.yml`
- `agent/entrypoint.sh`
- `agent/README.md`
- `docs/architecture/deployments/lux_vm_layout.md`

Changes:
- Add a new named volume: `agent_host_keys`.
- Mount it into `agent` as `rw` at `/persist/ssh_host_keys`.
- Update `agent/entrypoint.sh` startup sequence:
  - Before starting `sshd`, restore host keys from `/persist/ssh_host_keys` to
    `/etc/ssh` when present.
  - If missing, run `ssh-keygen -A` once and persist generated keys to
    `/persist/ssh_host_keys`.
  - Apply explicit ownership/permissions for private/public key files.
- Keep existing `authorized_keys` sync behavior unchanged.

Key files to persist (matching `agent/sshd_config`):
- `/etc/ssh/ssh_host_rsa_key` (+ `.pub`)
- `/etc/ssh/ssh_host_ecdsa_key` (+ `.pub`)
- `/etc/ssh/ssh_host_ed25519_key` (+ `.pub`)

### 2) Enforce `accept-new` in Harness SSH Client

Files:
- `harness/harness.py`
- `harness/README.md`

Changes:
- In `ssh_base_args()`, replace:
  - `StrictHostKeyChecking=no`
- With:
  - `StrictHostKeyChecking=accept-new`
- Keep:
  - `UserKnownHostsFile=/harness/keys/known_hosts`

Expected behavior:
- First connection to an unknown `agent` key is accepted and written.
- A changed key for an existing host alias is rejected (secure default).

### 3) One-Time Migration for Existing Environments

Files:
- `harness/README.md` (Troubleshooting section)
- optionally `docs/contracts/install.md` (upgrade note)

Changes:
- Document one-time stale-key cleanup when migrating existing volumes:

```bash
docker compose ... exec -T harness \
  ssh-keygen -f /harness/keys/known_hosts -R agent
docker compose ... exec -T harness \
  ssh-keygen -f /harness/keys/known_hosts -R '[agent]:22'
```

- After cleanup, next SSH connection stores the persisted host key via
  `accept-new`.

## Verification Plan

### Local Smoke

1. `lux up --collector-only --wait`
2. `lux up --provider codex --wait`
3. Compare fingerprints from inside harness:
   - `ssh-keyscan -p 22 agent | ssh-keygen -lf -`
   - `ssh-keygen -lf /harness/keys/known_hosts`
4. Restart only `agent` container.
5. Re-compare fingerprints and confirm unchanged.
6. Run `lux tui --provider codex` and verify no host-key mismatch warning in
   session `stdout.log`.

### Regression Gates

1. `uv run pytest tests/integration/test_agent_codex_tui.py -q`
2. `uv run pytest tests/integration/test_agent_codex_tui_concurrent.py -q`
3. `uv run python scripts/all_tests.py --lane fast`

## Risks And Mitigations

- Risk: Existing stale `known_hosts` causes immediate reject with `accept-new`.
  - Mitigation: explicit one-time cleanup step in docs.
- Risk: bad key file perms prevent `sshd` startup.
  - Mitigation: explicit `chmod/chown` in entrypoint before launching `sshd`.
- Risk: scope growth into unrelated SSH refactors.
  - Mitigation: limit to volume persistence + one harness SSH option + docs/tests.

## Rollback

1. Revert `StrictHostKeyChecking` to previous value in `harness/harness.py`.
2. Revert agent host-key persistence logic and remove `agent_host_keys` volume.
3. Re-deploy provider plane.

## Review Checklist

- [ ] Mount path and volume naming are acceptable.
- [ ] We want strict `accept-new` behavior for changed keys.
- [ ] One-time migration command UX is acceptable.
- [ ] Proposed test scope is sufficient for this PR.
