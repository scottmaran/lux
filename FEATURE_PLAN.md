# Feature Plan: CLI Install/Setup/Uninstall Hardening and Pytest Migration

Date: 2026-02-12
Owner: codex subagent
Status: Draft for review

## 1. Goals

1. Migrate all CLI behavior testing from `scripts/cli_scripts/` into pytest/Python.
2. Fully remove `--remove-data` from `lasso uninstall`.
3. Make uninstall resilient even when config is invalid or missing.
4. Add deterministic, automated installer and real update coverage without external network dependency.
5. Remove the `12_missing_ghcr_auth` CLI-script test case (do not re-implement it in pytest); keep any remaining GHCR references accurate and consistent with the codebase.
6. Remove custom install location support for now: one fixed install layout under `$HOME` (`~/.lasso`, `~/.local/bin`, `~/.config/lasso`).
7. Keep unconditional cleanup at the end of every test as a hard invariant.

## 2. Locked Decisions

1. `scripts/cli_scripts/` will be deprecated and then deleted.
2. The GHCR-auth negative test case (`12_missing_ghcr_auth`) is removed and not replaced in pytest. GHCR references may remain in docs/code if they are accurate and current.
3. `--remove-data` is removed from CLI and docs.
4. Installer verification is a required PR gate in intent, but temporarily disabled like other PR gates.
5. Add a test hook to run install/update end-to-end against a local test release server.
6. Remove `--install-dir/--bin-dir/--config-dir` from `install_lasso.sh` and remove `LASSO_INSTALL_DIR`/`LASSO_BIN_DIR` overrides from the CLI runtime path model. Install paths are derived solely from `$HOME`.

## 3. Scope

In scope:
- `lasso` CLI command surface and behavior around install/setup/uninstall/update.
- Pytest integration coverage replacement for former bash CLI suite.
- Release-bundle alignment and testability hooks.
- Documentation updates for user and testing contracts.

Out of scope:
- New product features unrelated to install/setup/uninstall/update lifecycle.
- GHCR auth UX improvements (explicitly removed from test scope).

## 4. Implementation Workstreams

## A. Pytest-Only CLI Test Migration

Implementation:
1. Add Python integration tests that directly execute `lasso` via `subprocess`.
2. Replace script-by-script wrappers with behavior-driven pytest modules.
3. Preserve deterministic environment setup per test with isolated temp roots.
4. Enforce teardown in `finally` or fixture finalizers with compose `down -v --remove-orphans`.
5. Remove `tests/integration/test_cli_script_suite.py`.
6. Remove `scripts/cli_scripts/` after parity is complete.

Proposed test modules:
1. `tests/integration/test_cli_config_and_doctor.py`
2. `tests/integration/test_cli_lifecycle.py`
3. `tests/integration/test_cli_paths_uninstall.py`
4. `tests/integration/test_cli_update.py`
5. `tests/integration/test_cli_installer.py`

Test isolation rule (non-negotiable):
- Installer/update/uninstall tests must run with an isolated temporary `HOME`, so the fixed install layout remains fully contained and cannot touch the developer machine’s real `~/.lasso`, `~/.local/bin`, or `~/.config/lasso`.
- Tests should execute the `lasso` binary via an explicit path inside the temp home (or by prepending the temp `~/.local/bin` to `PATH`), never relying on any pre-existing `lasso` in the host `PATH`.

## B. Remove `--remove-data` Completely

Implementation:
1. Remove `remove_data` argument from CLI parser in `lasso/src/main.rs`.
2. Remove all uninstall code paths that target `log_root` and `workspace_root`.
3. Ensure uninstall cannot delete runtime data directories under any flag.
4. Update CLI docs and test docs to remove `--remove-data` mentions.
5. Add tests that assert the flag is rejected and data dirs are preserved.

## C. Uninstall Guardrails and Error Handling

Implementation:
1. Refactor uninstall path resolution to work even when config load fails.
2. Use safe fallback paths for install/bin/config directories from env/defaults.
3. Keep `--remove-config` support, but treat invalid config as warning, not hard blocker.
4. Preserve current `--yes` and `--dry-run` semantics.
5. Keep stack shutdown attempt behavior with `--force` escape hatch.
6. Emit explicit JSON warnings for partial cleanup scenarios.

Coverage:
1. Unit tests in `lasso/tests/cli.rs` for invalid-config uninstall flows.
2. Integration tests validating dry-run plan and real removal behavior.
3. Assertions that workspace/log roots are never removed.

## D. Installer and Real Update End-to-End Test Hook

Implementation:
1. Add `LASSO_RELEASE_BASE_URL` override support.
2. `install_lasso.sh` uses hook URL when set; defaults to current GitHub release URL.
3. `lasso update` path uses same override in update plan URL construction.
4. Add pytest fixture that launches a local HTTP server hosting fake release artifacts.
5. Generate test bundles/checksums matching release workflow layout.
6. Cover real install, real update apply, and rollback behavior against local server.

Release-bundle alignment:
1. Treat release workflow artifact structure as source of truth.
2. Make installer/update robust to the current release tar layout (which includes a top-level directory), so install/update produce the expected `.../versions/<ver>/lasso` path.
3. Keep backward compatibility with older “flat” bundles if they exist.

## E. Remove GHCR-Related Test Surface

Implementation:
1. Delete `scripts/cli_scripts/12_missing_ghcr_auth.sh` and remove it from any runners (`run_all.sh`, pytest wrappers, docs under `scripts/cli_scripts/`).
2. Do not port this GHCR-auth negative case into the new pytest suite.
3. Keep GHCR references elsewhere (e.g. user install docs) only if they match reality for the current release (private vs public images, `docker login ghcr.io` requirements, etc).

## F. Gate and Workflow Updates

Implementation:
1. Add installer verification job in `.github/workflows/ci-pr.yml`.
2. Mark it temporarily disabled with clear TODO note, matching current disabled-gate pattern.
3. Keep canonical local lane coverage in `scripts/all_tests.py` aligned with new pytest modules.
4. Remove obsolete references to `scripts/cli_scripts/run_all.sh`.

## G. Documentation and Contract Updates

Files to update:
1. `docs/guide/cli.md`
2. `docs/guide/install.md`
3. `tests/README.md`
4. `docs/history/HISTORY.md`
5. `docs/history/dev_log.md`

Required doc outcomes:
1. No `--remove-data` references remain.
2. CLI testing is described as pytest/Python only.
3. Installer/update testing explains local release hook usage for deterministic validation.
4. No stale GHCR references in docs (GHCR can be mentioned, but must be consistent with the current code and release posture).

## 5. Acceptance Criteria

1. No tests depend on `scripts/cli_scripts/`.
2. `scripts/cli_scripts/` is deleted or fully unused and scheduled for deletion in same change.
3. `lasso uninstall` has no `--remove-data` option.
4. Uninstall succeeds in cleanup mode even with invalid config (with explicit warnings where relevant).
5. Installer test is automated in pytest and runs without external network.
6. Update apply and rollback have real mutation-path coverage in pytest.
7. `12_missing_ghcr_auth` is removed and not re-implemented in pytest.
8. Every docker-backed test has unconditional teardown.
9. Updated docs are consistent with runtime behavior and test architecture.
10. Installer/update/uninstall tests do not modify the host’s real `~/.lasso`, `~/.local/bin`, or `~/.config/lasso` (validated by running tests with a temp `HOME`).

## 6. Validation Plan

1. `cargo test -q --manifest-path lasso/Cargo.toml`
2. `uv run pytest tests/integration/test_cli_config_and_doctor.py -q`
3. `uv run pytest tests/integration/test_cli_lifecycle.py -q`
4. `uv run pytest tests/integration/test_cli_paths_uninstall.py -q`
5. `uv run pytest tests/integration/test_cli_update.py -q`
6. `uv run pytest tests/integration/test_cli_installer.py -q`
7. `uv run pytest tests/integration -m "integration and not agent_codex" -q`
8. `uv run python scripts/all_tests.py --lane pr --skip-contract`

## 7. Risks and Mitigations

1. Risk: installer/update hook diverges from production flow.
Mitigation: default path unchanged; hook only overrides base URL.

2. Risk: uninstall fallback behavior may miss some edge paths.
Mitigation: explicit JSON reporting of planned/removed/missing/warnings and added tests.

3. Risk: deleting bash scripts may remove useful ad-hoc tooling.
Mitigation: replace all behavior with pytest equivalents before deletion.

## 8. Execution Order

1. Add test hook support in installer and update code.
2. Implement pytest replacements for CLI coverage.
3. Remove `12_missing_ghcr_auth` coverage (and do not re-add it in pytest).
4. Remove `--remove-data` and harden uninstall fallback behavior.
5. Delete deprecated `scripts/cli_scripts/` and remove references.
6. Update docs and workflows.
7. Run full validation set.
