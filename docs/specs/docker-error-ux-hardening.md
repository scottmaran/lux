# Spec: Docker Error UX Hardening For Lux CLI

Status: implemented
Owner: codex
Created: 2026-02-18
Last updated: 2026-02-18

## Problem
Docker-related failures from lifecycle commands are currently surfaced as generic process failures. Users often get raw stderr without clear classification or direct remediation, especially for compose-plugin lookup and daemon/connectivity failures.

## Goals
- Classify common Docker/Compose failures into stable machine-readable error codes.
- Preserve existing top-level `error` text for compatibility while adding structured JSON error details.
- Include command context (`docker compose ...`) in process failures so users know what operation failed.
- Extend `doctor` to explicitly check both Docker daemon availability and Docker Compose plugin availability.
- Add test coverage so these UX guarantees remain enforced.

## Non-Goals
- Redesigning all CLI output envelopes.
- Changing non-Docker command error behavior outside additive metadata and clearer text.
- Supporting Docker variants that do not expose stderr/stdout in standard ways.

## User Experience
- `lux --json ...` failures keep the existing `error` field, and additionally include `error_details` with:
  - `error_code` (stable identifier)
  - `hint` (actionable remediation when known)
  - `command` (stringified Docker command context, when applicable)
  - `raw_stderr` (trimmed stderr text when available)
- Non-JSON failures print a clearer one-line process error that includes command context and, when known, a hint.
- `lux doctor --json` includes a separate compose capability check.

## Design
- Introduce an internal process-error metadata struct carried by `LuxError::Process`:
  - message: existing human-readable string used by Display.
  - details: optional structured payload for JSON wrappers.
- Add Docker error classification in `execute_docker`:
  - `docker_not_found`
  - `docker_compose_unavailable`
  - `docker_daemon_unreachable`
  - `docker_registry_auth`
  - `docker_compose_flag_unsupported`
  - `docker_port_conflict`
  - `docker_compose_wait_timeout`
- Add command-context rendering to `execute_docker` messages (for example, `docker compose --env-file ... ps ...`).
- Add doctor compose check by invoking `docker compose version` and report:
  - `checks.docker`
  - `checks.docker_compose`
  - `checks.log_root_writable`
- Keep compatibility:
  - Preserve the top-level `error` string in JSON wrapper.
  - Add `error_details` as an optional additive field.

## Data / Schema Changes
- CLI JSON error envelope is extended with optional `error_details` object.
- No collector/harness artifact schema changes.

## Security / Trust Model
- No trust-boundary changes.
- Improves operator clarity around Docker prerequisites without weakening invariants.

## Failure Modes
- Unknown Docker stderr patterns remain classified as `process_command_failed` with no hint.
- Doctor may report both daemon and compose unavailable; error text should mention both checks deterministically.

## Acceptance Criteria
- Lifecycle command failures include command context in error text.
- `--json` failures include `error_details.error_code` for known Docker failure classes.
- Compose-plugin-missing failures include an explicit hint about `DOCKER_CONFIG`/compose plugin setup.
- `doctor --json` reports `checks.docker_compose` and sets `ok=false` when compose is unavailable.
- Existing callers that only read `error` continue to work unchanged.

## Test Plan
- Unit tests (`lux`):
  - Docker stderr classification map to expected `error_code` + `hint`.
  - JSON error wrapper includes additive `error_details`.
  - Doctor compose check appears in JSON result.
- Integration tests:
  - Existing missing-docker path still fails cleanly.
  - HOME-isolated lifecycle tests remain green when Docker config is provided (already covered).
  - Add focused integration assertion for `doctor` compose check field.

## Rollout
- Stealth mode: no backward compatibility promises required, but this is additive.
- Update CLI contract docs for JSON error details and doctor checks.

## Open Questions
- None.

## Implementation Notes
- Implemented in:
  - `lux/src/main.rs`
  - `lux/tests/cli.rs`
  - `tests/integration/test_cli_config_and_doctor.py`
  - `docs/contracts/cli.md`
- Verification:
  - `cargo test` (from `lux/`) passed.
  - `uv run pytest tests/integration/test_cli_config_and_doctor.py -q` passed.
  - `uv run python scripts/all_tests.py --lane fast` passed.
