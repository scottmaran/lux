# Audit: Lux hard-rename spec consistency review

ID: 20260218-133939
Date: 2026-02-18
Owner: codex
Scope: Line-by-line audit of `docs/specs/lux-hard-rename.md` against current contracts, implementation, tests, and release workflows.

## Summary
The draft spec is directionally strong and aligned with the requested hard-break rename, but it currently has one high-impact factual mismatch and several medium gaps that can cause incomplete rename coverage.

Recommended next action: patch the spec before implementation to lock in complete, testable rename scope.

## Method
- Reviewed `docs/specs/lux-hard-rename.md` line by line.
- Cross-checked runtime/config/update behavior in `lasso/src/main.rs`.
- Cross-checked compose wiring in `compose.yml` and `compose.ui.yml`.
- Cross-checked installer/update surfaces in `install_lasso.sh` and `docs/contracts/install.md`.
- Cross-checked contract docs under `docs/contracts/*` and UI defaults in `ui/server.py`.
- Cross-checked test/workflow env and naming surfaces in `tests/*` and `.github/workflows/*`.

## Findings

### Finding: Runtime socket default path is misstated in the spec
Severity: high
Evidence:
- Spec says runtime socket default should become `/run/lux/runtime/control_plane.sock` (`docs/specs/lux-hard-rename.md:110`).
- Runtime contract defines default as `<config_dir>/runtime/control_plane.sock` (`docs/contracts/runtime_control_plane.md:10`).
- Implementation computes host default as `config_dir/runtime/control_plane.sock` (`lasso/src/main.rs:1476`).
- `/run/lasso/runtime/...` is currently container mount path for UI proxy, not host default (`compose.ui.yml:7`, `compose.ui.yml:13`).

Impact:
- Implementing this literally would change runtime behavior, not just rename identity.
- Risk of breaking runtime permission model and socket discovery across CLI/UI.

Recommendation:
- Update spec wording to preserve host default semantics:
  - Host default: `<config_dir>/runtime/control_plane.sock` (renamed via config dir move to `~/.config/lux`).
  - UI container mount path: `/run/lux/runtime/control_plane.sock`.

### Finding: `LASSO_*` environment inventory in the spec is incomplete for a hard break
Severity: high
Evidence:
- Spec lists selected env vars (`docs/specs/lux-hard-rename.md:84`, `docs/specs/lux-hard-rename.md:87`) while goal claims all `LASSO_*` surfaces (`docs/specs/lux-hard-rename.md:18`).
- Runtime bypass env exists but is not called out: `LASSO_RUNTIME_BYPASS` (`lasso/src/main.rs:30`).
- Test/CI knobs still use `LASSO_*` (for example `LASSO_STRESS_TRIALS` in `tests/stress/test_concurrent_job_stress.py:27`, plus external-install envs in `tests/external/test_external_install_from_github.py:54`).

Impact:
- Rename can ship with mixed env namespace and hidden old-name dependencies.
- Hard-break claim becomes unverifiable.

Recommendation:
- Add a dedicated spec section enumerating all `LASSO_*` variables by boundary (runtime, installer/update, provider wiring, tests, CI) and required `LUX_*` replacements.
- If any test-only envs are intentionally excluded, document explicit exceptions.

### Finding: Runtime fallback socket path names are not covered
Severity: medium
Evidence:
- Runtime fallback paths embed `lasso` in temp-socket names (`lasso/src/main.rs:1460`, `lasso/src/main.rs:1464`, `lasso/src/main.rs:1466`, `lasso/src/main.rs:1473`).
- Spec rename map only mentions `/run/lasso/...` runtime paths (`docs/specs/lux-hard-rename.md:61`).

Impact:
- Old product name can remain in filesystem/runtime diagnostics after rename.
- Violates full technical rename intent.

Recommendation:
- Explicitly include fallback socket path token rename requirements (including `/tmp` fallback names) and add regression tests for long socket-path fallback behavior.

### Finding: Docker project identity rename is under-specified
Severity: medium
Evidence:
- Current defaults set Docker project to `lasso` in config and code (`lasso/config/default.yaml:12`, `lasso/src/main.rs:449`, `docs/contracts/config.md:38`).
- Spec does not explicitly require renaming `docker.project_name` default/value.

Impact:
- Compose resources may continue using `lasso_*` names even after CLI/artifact rename.
- Produces mixed identity and potential test/docs drift.

Recommendation:
- Add `docker.project_name` to canonical rename map and acceptance criteria.
- Ensure default config template, docs, and integration harness expectations are updated accordingly.

### Finding: Release-source rename is not concrete enough for deterministic implementation
Severity: medium
Evidence:
- Release/update endpoints and user-agent are hardcoded today:
  - `LASSO_RELEASE_BASE_URL` default to `.../scottmaran/lasso/releases/download` (`lasso/src/main.rs:3053`, `lasso/src/main.rs:3054`, `install_lasso.sh:70`).
  - Latest-release API path uses `/repos/scottmaran/lasso/releases/latest` (`lasso/src/main.rs:3130`).
  - User-agent is `lasso-cli` (`lasso/src/main.rs:3135`, `lasso/src/main.rs:3151`).
- Spec only says “rename update endpoint defaults to the `lux` release source” (`docs/specs/lux-hard-rename.md:80`).

Impact:
- Implementers can satisfy bundle renames but still miss critical update/install endpoints.
- Update flows may silently fail post-cutover.

Recommendation:
- Specify exact default release endpoint behavior in the spec (repo slug, download base URL, and user-agent rename), plus tests that assert these values.

### Finding: UX statement about old command failure is too absolute
Severity: low
Evidence:
- Spec states `lasso` invocations fail because command/binary no longer exists (`docs/specs/lux-hard-rename.md:46`).
- Non-goals explicitly avoid migration/removal of old installs (`docs/specs/lux-hard-rename.md:28`), so old binaries can still exist on machines.

Impact:
- Sets an expectation that may not hold in upgraded environments with legacy binaries still present.

Recommendation:
- Reword to: new `lux` install does not install/link `lasso`; legacy `lasso` installs are unsupported.

## Suggested Work Items
- Patch `docs/specs/lux-hard-rename.md` to correct runtime socket default semantics and separate host default vs container mount path.
- Add explicit environment variable inventory table with required `LUX_*` replacements and any intentional exceptions.
- Extend canonical rename map to include `docker.project_name`, runtime temp fallback names, and release endpoint/user-agent defaults.
- Tighten acceptance criteria with deterministic checks (e.g., grep-based guards for active surfaces and update endpoint assertions).

## Verification Notes
- Commands run for this audit included:
  - `sed -n`/`nl -ba` on spec, contracts, compose, installer, workflow, and runtime source files.
  - `rg -n` sweeps for naming/env/path surfaces (`lasso`, `lasso__`, `LASSO_*`, `/run/lasso`, `lasso-runtime`).
- No code/tests/docs were modified outside this audit report.
