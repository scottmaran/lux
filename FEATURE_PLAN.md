# Feature Plan: Provider-Native CLI + Claude Support + Standardized Auth

## Status
- Scope: codex + claude first-class provider support with explicit auth modes

## Goals
- Replace provider-specific legacy UX (`--codex`) with explicit provider selection (`--provider`).
- Add first-class Claude support in both TUI and non-interactive run paths.
- Standardize provider/auth schema so future providers are simple to add.
- Separate collector lifecycle from provider lifecycle (`--collector-only` flow).
- Keep behavior explicit and deterministic (no hidden fallbacks, no auto-recreate).
- Add explicit test coverage and docs updates aligned with project philosophy.

## Definitions (Self-Contained)
- **Collector plane**: only the `collector` service and run-scoped log production.
- **Provider plane**: `agent` + `harness` services for one explicit provider (`codex` or `claude`).
- **`--collector-only`**: command targets only collector plane, never provider plane.
- **`--provider`**: command targets only provider plane for a named provider.
- **"conflicts with"**: CLI parser rejects passing both flags in the same command invocation.
- **Provider secrets file** (`~/.config/lasso/secrets/<provider>.env`): used only for `auth_mode=api_key`.
- **Host-state auth** (`auth_mode=host_state`): uses mounted host files only; no API-key secrets file required.

## Confirmed Decisions
- `--provider` is required for agent-facing actions.
- Remove `--codex` immediately (hard break, no alias).
- `auth_mode` is required and explicit: `api_key | host_state`.
- `mount_host_state_in_api_mode` is per-provider, default `false`.
- Host-state path resolution warns and continues if missing (including when all configured paths are missing).
- Provider mismatch is a hard-fail (no automatic container recreation).
- No `lasso run --env` secret guardrails (user responsibility).
- Use separate local secrets files under `~/.config/lasso/secrets/<provider>.env` for `auth_mode=api_key` only.
- Add local-only integration lanes for both `agent_codex` and `agent_claude`.
- Start with codex + claude only. No cloud-provider auth mode in this phase.

## Non-Goals
- No macOS Keychain bridge mode in this phase.
- No “inject full keychain” behavior.
- No cloud provider auth integrations (Bedrock/Vertex/etc.).
- No hidden provider defaults when provider is omitted (provider omission is invalid).

## Target CLI UX

### Lifecycle
- `lasso up --collector-only [--wait --timeout-sec N]`
- `lasso down --collector-only`
- `lasso status --collector-only`
- `lasso up --provider codex|claude [--wait --timeout-sec N]`
- `lasso down --provider codex|claude`
- `lasso status --provider codex|claude`

### Agent-facing actions
- `lasso tui --provider codex|claude`
- `lasso run --provider codex|claude "prompt" [--env KEY=VALUE ...]`

### Behavioral rules
- `--collector-only` conflicts with `--provider` (same command cannot include both).
- Agent-facing commands require a matching active provider stack; mismatch hard-fails.
- `up --provider X` does not silently switch provider if `Y` is already active.

### Command Semantics (Explicit)
- `lasso up --collector-only`:
  - starts collector plane only
  - creates/initializes active run state
  - does not start agent/harness
- `lasso up --provider <name>`:
  - requires collector plane and active run state already present
  - starts provider plane only (`agent` + `harness`) for that provider
  - hard-fails on provider mismatch if another provider plane is active
- `lasso down --collector-only`:
  - stops collector plane only
  - does not implicitly stop provider plane
- `lasso down --provider <name>`:
  - stops provider plane only for `<name>`
- `lasso run/tui --provider <name>`:
  - require active provider plane for `<name>`
  - hard-fail if missing or mismatched

## Proposed Config Schema

Use a provider map with explicit auth mode and provider defaults.
Notes:
- `auth.api_key.secrets_file` is read only when `auth_mode=api_key`.
- `auth.host_state.paths` are used when `auth_mode=host_state`.
- `mount_host_state_in_api_mode=true` allows optional host-state mounts even while `auth_mode=api_key`.

```yaml
version: 2

paths:
  log_root: ~/lasso-logs
  workspace_root: ~/lasso-workspace

release:
  tag: ""

docker:
  project_name: lasso

harness:
  api_host: 127.0.0.1
  api_port: 8081
  api_token: ""

providers:
  codex:
    auth_mode: api_key
    mount_host_state_in_api_mode: false
    commands:
      tui: "codex -C /work -s danger-full-access"
      run_template: "codex -C /work -s danger-full-access exec {prompt}"
    auth:
      api_key:
        secrets_file: ~/.config/lasso/secrets/codex.env
        env_key: OPENAI_API_KEY
      host_state:
        paths:
          - ~/.codex/auth.json
          - ~/.codex/skills
    ownership:
      root_comm:
        - bash
        - sh
        - setsid
        - timeout
        - codex

  claude:
    auth_mode: host_state
    mount_host_state_in_api_mode: false
    commands:
      tui: "claude"
      run_template: "claude -p {prompt}"
    auth:
      api_key:
        secrets_file: ~/.config/lasso/secrets/claude.env
        env_key: ANTHROPIC_API_KEY
      host_state:
        paths:
          - ~/.claude.json
          - ~/.claude
          - ~/.config/claude-code/auth.json
    ownership:
      root_comm:
        - bash
        - sh
        - setsid
        - timeout
        - claude
```

## Provider Auth Contracts (Initial)

### codex
- `auth_mode=api_key`
  - secrets file format: `OPENAI_API_KEY=<value>` (dotenv style, one `KEY=VALUE` per line)
  - secrets file permission target: `0600`
  - runtime bootstrap uses Codex API-key login flow and persists auth under `~/.codex`
- `auth_mode=host_state`
  - host-state defaults:
    - `~/.codex/auth.json`
    - `~/.codex/skills`

### claude
- `auth_mode=api_key`
  - secrets file format: `ANTHROPIC_API_KEY=<value>` (dotenv style, one `KEY=VALUE` per line)
  - secrets file permission target: `0600`
  - runtime bootstrap exports `ANTHROPIC_API_KEY` in the agent runtime context
- `auth_mode=host_state` (best-effort compatibility)
  - host-state defaults:
    - `~/.claude.json`
    - `~/.claude/`
    - `~/.config/claude-code/auth.json` if present
  - missing paths warn+continue by policy

### Why `claude` host-state can fail on macOS
- Claude authentication data on macOS can rely on Keychain-backed credential storage.
- Linux containers cannot access macOS Keychain directly.
- Result: mounted `~/.claude*` files may be insufficient for successful auth in-container.
- Expected behavior in this plan:
  - mount/copy host-state paths when configured
  - warn+continue if paths are missing
  - runtime auth may still fail
  - docs direct users to switch to `auth_mode=api_key` for deterministic container auth

## Architecture and Implementation Plan

### Phase 1: Config and Validation Refactor
Files:
- `lasso/src/main.rs`
- `lasso/config/default.yaml`
- `docs/guide/config.md`

Changes:
- Add provider config model (`providers.<name>...`) with strict validation.
- Bump schema version to `2`.
- Validate:
  - provider exists in config for requested `--provider`.
  - `auth_mode` is one of `api_key|host_state`.
  - provider command templates are non-empty.
  - ownership root_comm non-empty.
- Add config helpers for resolving:
  - effective mount behavior for current auth mode
  - secrets file path and env key
  - provider command defaults

Acceptance:
- `lasso config validate` fails with actionable errors on invalid provider/auth config.
- Default generated config includes both codex and claude entries.

### Phase 2: CLI Surface Changes
Files:
- `lasso/src/main.rs`
- `docs/guide/cli.md`
- `README.md`

Changes:
- Remove `--codex` options and code paths.
- Add required `--provider <codex|claude>` for:
  - `up` (when not `--collector-only`)
  - `down` (when not `--collector-only`)
  - `status` (when not `--collector-only`)
  - `tui`
  - `run`
- Add `--collector-only` to `up/down/status`.
- Add explicit argument conflict rules:
  - `--collector-only` conflicts with `--provider`.

Acceptance:
- Any use of legacy `--codex` fails immediately.
- Agent-facing commands fail when provider is missing.

### Phase 3: Lifecycle Split (Collector vs Provider Plane)
Files:
- `lasso/src/main.rs`
- `compose.yml` (if service list adjustments are needed)

Changes:
- `up --collector-only`: start collector only and initialize active run state.
- `up --provider X`: start agent+harness for provider `X` against active run; fail if collector/run state is absent.
- `down --collector-only`: stop collector only.
- `down --provider X`: stop agent+harness for provider `X`.
- `status --collector-only`: show collector service status.
- `status --provider X`: show provider plane status.

State model:
- Extend active state to include provider plane metadata (provider, auth_mode, started_at).
- Enforce provider mismatch hard-fail for `run/tui/up --provider`.

Acceptance:
- Collector can remain up while provider plane is cycled.
- Provider switch requires explicit down/up, never implicit recreation.

### Phase 4: Compose Wiring + Runtime Override Generation
Files:
- `lasso/src/main.rs`
- (new) generated runtime override path under config/runtime dir
- `compose.yml`
- `compose.codex.yml` (remove)
- (new optional static overlays if needed)

Changes:
- Move from static `compose.codex.yml` auth mounts to provider-driven runtime mount generation.
- Build runtime override files per command based on:
  - provider
  - auth_mode
  - `mount_host_state_in_api_mode`
  - existing host-state paths
  - provider secrets file mount (API mode only)
- Missing host-state paths:
  - warn to stderr
  - continue without mount

Acceptance:
- No hard dependency on static provider-specific compose mount files.
- Host-state optional mounts behave deterministically.

### Phase 5: Agent Bootstrap/Auth Standardization
Files:
- `agent/entrypoint.sh`
- `agent/Dockerfile`
- `agent/README.md`

Changes:
- Install both provider CLIs in the agent image (codex + claude).
- Add provider bootstrap contract via env vars:
  - `LASSO_PROVIDER`
  - `LASSO_AUTH_MODE`
  - `LASSO_PROVIDER_SECRETS_FILE`
  - `LASSO_PROVIDER_ENV_KEY`
  - `LASSO_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE`
- For `auth_mode=api_key`:
  - read provider secrets file and export provider env key in runtime shell context.
  - fail fast if secrets file is unreadable or required key is missing.
  - codex-specific bootstrap uses API key flow consistent with Codex docs.
- For `auth_mode=host_state`:
  - copy mounted host-state files into provider runtime home paths.
- For `auth_mode=api_key` + `mount_host_state_in_api_mode=true`:
  - perform host-state copy if mounts exist.

Acceptance:
- Codex API mode and host-state mode both function through standardized provider schema.
- Claude API mode and host-state mode are both wired; host-state remains best-effort on macOS.

### Phase 6: Harness Runtime Command Resolution
Files:
- `harness/harness.py`
- `harness/README.md`

Changes:
- Continue to use `HARNESS_TUI_CMD` and `HARNESS_RUN_CMD_TEMPLATE`.
- Ensure `lasso` always sets these from provider config before running `tui`/jobs.
- Keep existing root marker + PTY capture behavior unchanged.

Acceptance:
- Provider command defaults are config-driven, not hardcoded to codex at CLI orchestration level.

### Phase 7: Collector Ownership Refactor
Files:
- `collector/config/filtering.yaml`
- `collector/config/ebpf_filtering.yaml`
- `collector/scripts/filter_audit_logs.py`
- `collector/scripts/filter_ebpf_logs.py`
- `collector/entrypoint.sh`

Changes:
- Source ownership `root_comm` from provider-aware runtime config generated by lasso.
- Remove codex-only hardcoding from shipped defaults.
- Preserve current PID/SID lineage behavior.

Acceptance:
- Running with `provider=claude` produces owned rows without codex-only fallback gaps.
- Running with `provider=codex` preserves existing attribution correctness.

### Phase 8: Testing Plan

#### Unit
Files:
- `tests/unit/test_compose_contract_parity.py`
- `tests/unit/*` (new provider/config tests)

Coverage:
- required `--provider` argument behavior
- `--collector-only` conflicts and routing
- provider mismatch hard-fail behavior
- config schema version + provider validation
- runtime mount generation from auth mode/path existence
- removal of `--codex` behavior

#### Integration
Files:
- `tests/integration/*` (new/renamed provider tests)
- `tests/support/pytest_docker.py`
- `tests/support/integration_stack.py`

Coverage:
- collector-only up/down/status
- provider plane up/down/status
- `tui --provider codex` and `tui --provider claude`
- `run --provider codex` and `run --provider claude`
- provider mismatch hard-fail
- host-state missing paths warn+continue

Markers/Lanes:
- keep `agent_codex`
- add `agent_claude` local-only marker
- add lane support for codex and claude in `scripts/all_tests.py`

#### Regression
- Add focused regression for provider switch mismatch semantics and explicit failure modes.

Acceptance:
- `uv run python scripts/all_tests.py --lane codex` passes with local codex prerequisites.
- `uv run python scripts/all_tests.py --lane claude` passes with local claude prerequisites.

### Phase 9: Documentation Updates
Files:
- `README.md`
- `docs/guide/cli.md`
- `docs/guide/config.md`
- `docs/orientation/platform.md`
- `docs/dev/DEVELOPING.md`
- `agent/README.md`
- `harness/README.md`
- `collector/README.md` (if needed for ownership config behavior)
- `docs/history/dev_log.md` (implementation log entry after merge)

Required updates:
- new provider-required command examples
- collector-only lifecycle workflow
- provider/auth_mode schema and secrets-file setup
- codex + claude setup guides
- clear explanation that secrets files are API-mode-only inputs
- clear explanation of `--collector-only` vs `--provider` command scope/conflicts
- detailed note for claude host-state on macOS:
  - why file mounts may be insufficient
  - expected failure symptoms
  - recommended fallback to `auth_mode=api_key`
- explicit note that `lasso run --env` values are persisted in job metadata

## Migration and Breaking Changes
- Breaking CLI change: `--codex` removed.
- Config schema update to `version: 2`.
- Add migration notes:
  - how to update old config to provider schema
  - how to create `~/.config/lasso/secrets/codex.env` (`OPENAI_API_KEY=...`, `chmod 600`)
  - how to create `~/.config/lasso/secrets/claude.env` (`ANTHROPIC_API_KEY=...`, `chmod 600`)

## Security Notes (Local-Dev Scope)
- Provider secrets are scoped to the selected provider and auth mode.
- No implicit host-state mounts in API mode unless explicitly enabled per provider.
- Host-state auth for claude is best-effort in Linux containers when macOS keychain-backed auth is used on host.
- No additional restrictions on `lasso run --env` in this phase by explicit product decision.

## Open Risks
- Claude host-state compatibility may vary across host setups and Claude CLI changes.
- Provider command defaults may require tuning as upstream CLIs evolve.
- Lifecycle split complexity requires careful state handling to avoid stale active provider metadata.

## Final Acceptance Criteria
- Provider-driven flow works end-to-end for codex and claude in TUI and run modes.
- Collector can be managed independently via `--collector-only`.
- Provider/auth config is explicit, validated, and documented.
- Local-only provider-specific test lanes exist and pass with prerequisites.
- Legacy codex flag path is fully removed from code, tests, and docs.
