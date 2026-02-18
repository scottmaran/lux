# Audit: Lux hard-rename spec second-pass consistency review

ID: 20260218-134809
Date: 2026-02-18
Owner: codex
Scope: Second-pass implementation-readiness review of `docs/specs/lux-hard-rename.md` after initial fixes.

## Summary
The spec is now largely correct and implementation-ready. I did not find additional high-severity inaccuracies. I found three medium gaps and one low-clarity issue that could leave residual `lasso` naming in active runtime/test surfaces.

## Method
- Re-read `docs/specs/lux-hard-rename.md` line-by-line.
- Cross-checked active runtime/agent/harness/test/workflow surfaces for `lasso` and `LASSO_*` usage.
- Focused on implementation surfaces (not historical docs) to identify remaining contract omissions.

## Findings

### Finding: Harness root marker path token rename is not explicitly covered
Severity: medium
Evidence:
- Active harness runtime marker paths still embed `lasso`:
  - `harness/harness.py:167`
  - `harness/harness.py:171`
- Unit tests assert those exact path tokens:
  - `tests/unit/test_harness_markers.py:29`
  - `tests/unit/test_harness_markers.py:36`
  - `tests/unit/test_harness_markers.py:50`
  - `tests/unit/test_harness_markers.py:51`
- Current spec rename map covers runtime socket fallback tokens but not harness marker file tokens (`docs/specs/lux-hard-rename.md:64`, `docs/specs/lux-hard-rename.md:65`).

Impact:
- Hard-break rename can ship with active runtime artifacts still named `lasso_root_*`.
- Leaves observable old-name residue in attribution-related paths.

Recommendation:
- Add explicit rename requirement for root marker paths:
  - `/tmp/lasso_root_pid_<id>.txt` -> `/tmp/lux_root_pid_<id>.txt`
  - `/tmp/lasso_root_sid_<id>.txt` -> `/tmp/lux_root_sid_<id>.txt`
- Add unit/integration regressions in the test plan for these paths.

### Finding: Provider auth export-script filename rename is not specified
Severity: medium
Evidence:
- Active entrypoint path token:
  - `agent/entrypoint.sh:12` (`/etc/profile.d/lasso-provider-auth.sh`)
- Contract doc references same filename:
  - `agent/provider_auth.md:83`
- Spec provider wiring section only calls out env keys and `/run/lasso/...` mounts (`docs/specs/lux-hard-rename.md:131` to `docs/specs/lux-hard-rename.md:139`).

Impact:
- Provider auth can remain partially branded as `lasso` even after rename.

Recommendation:
- Add this file token to canonical rename map and provider-wiring acceptance checks.

### Finding: Internal temp/sentinel naming tokens are not enumerated
Severity: medium
Evidence:
- Setup writable-check sentinel:
  - `lasso/src/main.rs:1568` (`.lasso_write_test`)
- Update temporary download directory token:
  - `lasso/src/main.rs:3355` (`lasso-update-*`)
- Spec currently covers runtime fallback temp socket names but not these additional temp/sentinel tokens.

Impact:
- Full technical rename intent can be interpreted inconsistently (some runtime temp artifacts renamed, others not).

Recommendation:
- Add a line in the canonical map or implementation boundaries requiring rename of internal temp/sentinel tokens used by setup/update probes.

### Finding: “All active `LASSO_*` variables” wording is slightly ambiguous
Severity: low
Evidence:
- Spec claims all active `LASSO_*` variables are renamed (`docs/specs/lux-hard-rename.md:74`).
- Repository also contains `LASSO_*`-prefixed test token literals that are not env vars:
  - `tests/integration/test_agent_codex_exec.py:30`
  - `tests/integration/test_agent_codex_tui.py:39`

Impact:
- Minor ambiguity for implementers who may over-interpret the env-inventory section.

Recommendation:
- Clarify heading text to “All active `LASSO_*` environment variables” (explicitly env vars only).

## Suggested Work Items
- Patch `docs/specs/lux-hard-rename.md` to include harness marker-path and provider profile-script filename renames.
- Add internal temp/sentinel token rename requirements for setup/update internals.
- Clarify env-inventory wording scope to environment variables only.

## Verification Notes
- Verification commands were read-only (`sed`, `nl`, `rg`) across active implementation surfaces.
- No code or contract behavior was changed in this audit pass.
