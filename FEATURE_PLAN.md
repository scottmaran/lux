# Feature Plan: Install/Update/Uninstall Hardening + Pytest-Only CLI Tests

Date: 2026-02-12
Owner: codex subagent
Status: Draft for review

## 1. Why This Work

We are approaching beta and the highest-risk user lifecycle is:

1. Install the CLI (and bundle files).
2. Configure and start the stack.
3. Update to a new version and rollback if needed.
4. Uninstall safely, even when config is missing or invalid.

Today, parts of this lifecycle are under-tested, and there is a release-bundle layout mismatch between the release workflow and the installer/updater extraction expectations.

## 2. Goals (Locked)

1. Move all CLI behavior testing into pytest/Python. Deprecate and delete `scripts/cli_scripts/`.
2. Add deterministic installer and real update coverage that does not depend on external network or GitHub Releases.
3. Fully remove `lasso uninstall --remove-data` (and all code/docs/tests mentioning it).
4. Make uninstall resilient when config is missing or invalid (uninstall should still remove the installed CLI footprint).
5. Remove only the `12_missing_ghcr_auth` negative test case (do not re-implement it in pytest). Keep GHCR references elsewhere if accurate and current.
6. Fully remove custom install location support for now. Install layout is fixed under `$HOME`:
   - `~/.lasso` (versions + `current` symlink)
   - `~/.local/bin/lasso` (symlink to the current CLI)
   - `~/.config/lasso` (config + compose env)
7. Enforce unconditional cleanup in every docker-backed test and in every installer/update/uninstall test (no host pollution).

## 3. Non-Goals

1. GHCR auth UX improvements (we are only removing the GHCR-auth negative test case).
2. New product features unrelated to install/setup/uninstall/update.
3. Re-introducing custom install paths now (we can revisit after beta).

## 4. Key Findings to Address

1. Release bundle layout mismatch:
   - `.github/workflows/release.yml` tars a top-level directory named like `lasso_<ver>_<os>_<arch>/...`.
   - `install_lasso.sh` and `lasso update` currently extract into `.../versions/<ver>` and then assume files are directly at `.../versions/<ver>/lasso`, which will be false if the tar contains the top-level directory.
2. Uninstall currently depends on parsing config when config exists, which makes uninstall brittle when config is invalid. This is unacceptable for uninstall.
3. Custom install dir/bin dir behavior is currently "split brain":
   - The installer can install to arbitrary locations, but the CLI defaults for update/uninstall/paths assume `~/.lasso` and `~/.local/bin` unless env overrides are set.
   - This creates surprising outcomes and complicates tests.
4. Current CLI bash suite and pytest wrapper mask some fragility; we want pytest-native tests with strong isolation invariants.

## 5. Proposed Implementation

### A) Fixed Install Layout (Remove Custom Install Dirs)

Changes:
1. `install_lasso.sh`:
   - Remove flags: `--install-dir`, `--bin-dir`, `--config-dir`.
   - Always install under `$HOME` fixed layout.
2. `lasso` CLI:
   - Remove `LASSO_INSTALL_DIR` and `LASSO_BIN_DIR` overrides from runtime path resolution.
   - Continue to support config overrides (`--config`, `LASSO_CONFIG`, `LASSO_CONFIG_DIR`, `LASSO_ENV_FILE`) as they do not affect install layout.
3. Update docs to reflect fixed layout and remove any mention of custom install dirs.

Acceptance:
- No code path depends on a configurable install/bin directory.
- `lasso paths --json` still reports install/bin paths, but they are always derived from `$HOME`.

### B) Bundle Extraction Fix (Installer + Update Must Match Release Workflow)

We need a single rule:
- If the tar contains a single top-level directory, extraction must flatten into the version directory so that `.../versions/<ver>/lasso` exists.
- If the tar is "flat", extraction should still work.

Changes:
1. `install_lasso.sh`:
   - After extraction, ensure expected layout exists.
   - If extraction produced `DEST_DIR/<single-dir>/...`, flatten.
2. `lasso update apply`:
   - Update `extract_bundle()` or post-extract validation to support both layouts.
   - Fail with a clear error if the bundle layout is neither acceptable shape.

Acceptance:
- Installer and updater work with artifacts produced by `.github/workflows/release.yml` without special-casing in tests.

### C) Deterministic "Local Release Server" Hook (Installer + Update E2E Without External Network)

We will add a test hook that only affects tests (but is safe to ship as an opt-in env override).

Hook contract:
1. Add env var `LASSO_RELEASE_BASE_URL`:
   - Default: `https://github.com/scottmaran/lasso/releases/download`
   - Semantics: artifact URL is `${LASSO_RELEASE_BASE_URL}/${VERSION}/${BUNDLE_NAME}`
2. `install_lasso.sh` uses `LASSO_RELEASE_BASE_URL` if set.
3. `lasso update apply` uses the same base for `bundle_url` and `checksum_url`.
4. Tests will avoid `update check` (which calls the GitHub API) by always running `lasso update apply --to vX.Y.Z`.

How fake release artifacts are produced (pytest fixture):
1. Build or reuse a local `lasso` binary from the current source tree for the host platform.
2. Assemble a directory exactly like the release workflow:
   - `dist/lasso_<ver>_<os>_<arch>/lasso`
   - `dist/lasso_<ver>_<os>_<arch>/compose.yml`
   - `dist/lasso_<ver>_<os>_<arch>/compose.codex.yml`
   - `dist/lasso_<ver>_<os>_<arch>/compose.ui.yml`
   - `dist/lasso_<ver>_<os>_<arch>/config/default.yaml`
   - `dist/lasso_<ver>_<os>_<arch>/README.md` and `VERSION` (optional but preferred to match release)
3. Create `lasso_<ver>_<os>_<arch>.tar.gz` containing that top-level directory.
4. Create `lasso_<ver>_<os>_<arch>.tar.gz.sha256` formatted for `shasum -c` / `sha256sum -c`.
5. Serve the directory with a local HTTP server such that:
   - `${BASE}/vX.Y.Z/lasso_<ver>_<os>_<arch>.tar.gz` resolves
   - `${BASE}/vX.Y.Z/lasso_<ver>_<os>_<arch>.tar.gz.sha256` resolves

Acceptance:
- `install_lasso.sh` and `lasso update apply` can be tested end-to-end using only `localhost`.

### D) Remove `lasso uninstall --remove-data` Completely

Changes:
1. Remove the `remove_data` flag from clap and all uninstall target logic that removes `log_root` and `workspace_root`.
2. Update docs (`docs/guide/cli.md`, `docs/guide/install.md`) and test docs to remove mentions.
3. Add tests asserting:
   - `lasso uninstall --remove-data` is rejected (exit non-zero with clear message).
   - uninstall never plans or deletes log/workspace roots under any option.

Acceptance:
- There is no CLI flag or code path that recursively deletes user-provided log/workspace directories.

### E) Uninstall Resilience When Config Is Invalid or Missing

Principle:
- Uninstall must be able to remove the installed CLI footprint even when config cannot be parsed.

Changes:
1. Refactor uninstall to avoid reading/parsing `config.yaml` at all (unless a specific future option truly requires it).
2. Uninstall target computation should be based on:
   - fixed install layout under `$HOME`
   - known config/env file paths (which come from CLI args/env and do not require parsing YAML)
3. Preserve safety controls:
   - Require `--yes` unless `--dry-run`.
   - Keep `--force` to skip pre-uninstall stack shutdown.
4. Keep JSON output detailed: planned/removed/missing, plus warnings if anything fails.

Acceptance:
- `lasso uninstall --yes --force` succeeds even if `~/.config/lasso/config.yaml` exists but is invalid YAML.

### F) Pytest-Only CLI Test Migration (Replace Bash Suite)

Strategy:
- Replace script-by-script coverage with behavior-driven pytest modules that call the CLI via `subprocess`.

New pytest modules (proposed):
1. `tests/integration/test_cli_config_and_doctor.py`
2. `tests/integration/test_cli_lifecycle.py`
3. `tests/integration/test_cli_paths_uninstall.py`
4. `tests/integration/test_cli_update.py`
5. `tests/integration/test_cli_installer.py`

Non-negotiable isolation rules:
1. Installer/update/uninstall tests run with a temporary isolated `HOME`.
   - This guarantees the fixed install layout creates symlinks only under the temp home.
   - Teardown is deleting the temp home directory.
2. Tests execute the `lasso` binary by explicit path inside the temp home (or by prepending the temp `~/.local/bin` to `PATH`).
3. Tests that interact with Docker must always teardown with `docker compose down --volumes --remove-orphans` in a `finally`/fixture-finalizer.

Removal plan:
1. Delete `tests/integration/test_cli_script_suite.py`.
2. Delete `scripts/cli_scripts/` after pytest parity is complete.
3. Specifically remove `scripts/cli_scripts/12_missing_ghcr_auth.sh` and remove it from any runners immediately (do not port into pytest).

Acceptance:
- `uv run pytest` is the single source of truth for CLI behavior tests.

### G) CI Gate (Initially Disabled)

Changes:
1. Add an "installer verification" job to the PR workflow.
2. Keep it disabled initially (matching existing disabled gate patterns) but structured so enabling it is a one-line change later.
3. Ensure the job runs:
   - local release server hook installer test
   - real update apply + rollback test
   - uninstall tests

Acceptance:
- The job exists and is easy to enable as a required PR gate when ready.

### H) Docs Updates (Up To Date, Not "No GHCR")

Changes:
1. Remove all mentions of `--remove-data`.
2. Update install docs to match the fixed install layout and current install script behavior.
3. Keep GHCR references only if consistent with:
   - current compose image references (`ghcr.io/...`)
   - current public/private image posture
   - current CLI error messages and guidance

Acceptance:
- Docs are consistent with code and not stale.

## 6. Acceptance Criteria (Summary Checklist)

1. `install_lasso.sh` has no custom directory flags and installs only into the fixed `$HOME` layout.
2. `lasso` no longer supports `LASSO_INSTALL_DIR` or `LASSO_BIN_DIR`.
3. Installer and updater correctly handle the release tar layout produced by `.github/workflows/release.yml`.
4. `LASSO_RELEASE_BASE_URL` enables fully local installer + update apply/rollback tests.
5. `lasso uninstall` has no `--remove-data` option and never deletes log/workspace roots.
6. Uninstall works even with invalid config present.
7. `scripts/cli_scripts/12_missing_ghcr_auth.sh` is removed and not replaced in pytest.
8. `scripts/cli_scripts/` is deleted and no tests depend on it.
9. Installer/update/uninstall tests do not modify the real host `~/.lasso`, `~/.local/bin`, or `~/.config/lasso` (validated by temp-`HOME` tests).

## 7. Validation Commands

1. `cargo test -q --manifest-path lasso/Cargo.toml`
2. `uv run pytest -q`
3. `uv run pytest tests/integration/test_cli_installer.py -q`
4. `uv run pytest tests/integration/test_cli_update.py -q`

## 8. Risks and Mitigations

1. Risk: local-release hook diverges from production behavior.
Mitigation: default remains GitHub; hook only changes the base URL for downloads.

2. Risk: bundle layout variability breaks extraction.
Mitigation: explicitly support both "single top-level directory" and "flat" layouts, with clear errors otherwise.

3. Risk: accidental host pollution from installer symlinks.
Mitigation: all installer/update/uninstall tests run under an isolated temp `HOME` and tear down by deleting it.

## 9. Execution Order

1. Fixed install layout changes (remove custom dirs in installer and CLI).
2. Bundle extraction fix (installer + updater) and add `LASSO_RELEASE_BASE_URL` hook.
3. Implement pytest local-release server fixture and installer/update/uninstall tests (temp `HOME`).
4. Remove `--remove-data` and refactor uninstall to be config-parse independent.
5. Remove `12_missing_ghcr_auth` and migrate remaining CLI scripts to pytest; then delete `scripts/cli_scripts/` and wrappers.
6. Update docs and add the disabled CI installer verification gate.
