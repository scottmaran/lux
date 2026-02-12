# Feature Plan: SID Marker Introduction (No Emission-Barrier Changes)

## Objective
Reduce misattributed `unknown` ownership in concurrent runs by adding a per-run Linux session marker (`SID`) and using it as an attribution fallback when root-PID lineage is not yet available.

This branch intentionally scopes to SID marker introduction only.

## Scope
In scope:
- Introduce `setsid`-based run markers in harness launch paths.
- Persist run `root_sid` metadata for jobs and TUI sessions.
- Extend collector attribution to use `root_sid` as a fallback after current PID-lineage checks.
- Enforce `root_sid` as required metadata for harness-launched attributed runs in validator checks.
- Keep ownership precedence deterministic and backward-compatible.
- Add/update tests and docs for SID semantics.

Out of scope (explicitly deferred):
- Any new emission barrier / deferral behavior for unknown rows.
- Changes to pending-buffer semantics.
- Changes to validator ownership shape policy (`unknown` + missing `job_id` remains invalid).
- Cgroup-based attribution changes.

## Why This Approach
Current attribution is strongest once `root_pid` is present, but concurrent startup timing can still emit rows before stable PID mapping is available. A run-level SID marker provides a second stable discriminator for concurrent sessions and preserves current pipeline behavior.

## Design
### 1) Harness: emit SID marker at run launch
Files:
- `harness/harness.py`

Planned changes:
- Extend run marker capture to persist both:
  - `root_pid` (existing)
  - `root_sid` (new)
- Update launch prefixes used by:
  - `run_job(...)` remote command path
  - `run_tui(...)` remote command path
- Introduce remote marker capture based on `setsid` + `/proc` so the launched run has a distinct session marker and metadata captures that value.
- Persist `root_sid` in:
  - `logs/jobs/<job_id>/input.json`
  - `logs/jobs/<job_id>/status.json`
  - `logs/sessions/<session_id>/meta.json`

Constraints:
- Keep current command semantics and TUI behavior unchanged.
- Keep existing `root_pid` behavior intact.
- `root_sid` should always be generated for harness-launched jobs/TUI sessions.

### 2) Collector: SID-aware run indexing and attribution fallback
Files:
- `collector/scripts/filter_audit_logs.py`
- `collector/scripts/filter_ebpf_logs.py`

Planned changes:
- Extend run index loading to ingest `root_sid` in addition to `root_pid`.
- Add process SID lookup helper(s) for live attribution (same caching model as `ns_pid` lookup).
- Attribution order remains deterministic:
  1. Existing root PID / parent-lineage mapping
  2. Existing cached PID-owner mapping
  3. New SID fallback (`process_sid -> session_id/job_id`)
  4. Existing unknown fallback
- Preserve current precedence rules (session ownership over job where both could match).

Constraints:
- No changes to unknown emission timing logic.
- No extra buffering/defer logic added.

### 3) Validator behavior
Files:
- `tests/conftest.py`

Planned handling:
- Keep validator ownership rules unchanged for this branch.
- Add `root_sid` completeness checks alongside `root_pid` completeness for referenced session/job owners.
- Treat missing/non-integer `root_sid` as invalid for referenced session/job owners (tests/fixtures updated accordingly).

## Test Plan
### Unit tests (required)
Files to update:
- `collector/tests/test_filter.py`
- `collector/tests/test_ebpf_filter.py`
- `tests/unit/test_harness_markers.py` (new file; required)
- bridge coverage remains through:
  - `tests/unit/test_audit_filter.py`
  - `tests/unit/test_ebpf_filter.py`

New/updated assertions:
- SID fallback attributes event to correct session when PID-root mapping is absent.
- Concurrent sessions with distinct SIDs do not cross-attribute.
- PID mapping remains preferred when available.
- Unknown behavior remains unchanged when neither PID nor SID can resolve.
- Harness run marker generation includes SID marker semantics in command construction/helpers.

### Integration/stress checks (targeted)
Files likely updated:
- `tests/integration/test_agent_codex_tui_concurrent.py` (stability assertions around session ownership evidence)
- `tests/regression/test_startup_attribution_race.py` (required focused regression for startup-attribution race)

Execution gates to run:
- `uv run pytest tests/unit -q`
- `uv run pytest tests/integration/test_agent_codex_tui_concurrent.py -q`
- `uv run pytest tests/regression/test_startup_attribution_race.py -q`
- `uv run pytest tests/regression -q`

## Documentation Plan
Files to update:
- `harness/README.md`
  - Document `root_sid` capture and intent (session marker semantics).
- `collector/config/filtering_rules.md`
  - Document attribution precedence including SID fallback.
- `docs/history/HISTORY.md`
  - Add entry for SID-marker attribution hardening.
- `docs/history/dev_log.md`
  - Add implementation details for harness/collector SID path and tests.
- `tests/README.md`
  - Clarify ownership mapping now uses root PID lineage with SID fallback and requires complete root markers (`root_pid`, `root_sid`) for referenced owners.

## Acceptance Criteria
- Concurrent run attribution materially improves for rows that previously landed as misattributed/unknown due to early PID mapping gaps.
- No changes in unknown emission timing semantics.
- No regression in existing PID-lineage ownership behavior.
- `root_sid` is present and integer in generated session/job metadata used for attribution.
- Updated docs match implemented behavior and test evidence.
