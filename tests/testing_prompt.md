# Lasso Testing Suite Implementation Prompt (Subagent)

You are implementing a full testing suite for Lasso on branch `robust_test_suite`.
This is not a brainstorming task. You are expected to design and ship the first
working end-to-end version of the suite and CI enforcement.

Read this prompt fully before coding. Treat it as the implementation contract.

## 0) Mission
Build a deterministic, comprehensive, maintainable test system such that:

- Passing required gates means: no known requirement violations in supported environments.
- The suite is usable identically by local developers and autonomous agents.
- CI enforces required behavior (not just docs/policy text).

Use `tests/README.md` as the authoritative philosophy and contract.

## 1) Required Context to Read First
Before making changes, read:

1. `tests/README.md` (source of truth for structure and policy)
2. `tests/test_principles.md` (if relevant for design language)
3. Collector scripts and tests:
   - `collector/scripts/filter_audit_logs.py`
   - `collector/scripts/filter_ebpf_logs.py`
   - `collector/scripts/summarize_ebpf_logs.py`
   - `collector/scripts/merge_filtered_logs.py`
   - `collector/tests/test_filter.py`
   - `collector/tests/test_ebpf_filter.py`
   - `collector/tests/test_ebpf_summary.py`
   - `collector/tests/test_merge_filtered.py`
4. Current integration and CLI scripts under:
   - `scripts/run_integration_*.sh`
   - `scripts/run_lasso_cli_integration.sh`
   - `scripts/cli_scripts/*`
5. Existing workflows:
   - `.github/workflows/release.yml`

Then produce implementation, not analysis.

## 2) Non-Negotiable Constraints
1. Use Python/pytest as the primary test language and orchestration layer.
2. New integration/stress tests must be Python-based (no new Bash test logic).
3. Keep one canonical command surface for local + CI execution.
4. Determinism + isolation are mandatory.
5. Include regression test pathway for bug fixes.
6. Enforce via CI + scripts, not docs-only guidance.

## 3) Deliverables (You Must Implement)

### A. Test Directory Scaffolding
Create/standardize:

```text
tests/
  conftest.py
  fixture/
    conftest.py
    schemas/
      case_schema.yaml
    audit_filter/
    ebpf_filter/
    summary/
    merge/
    pipeline/
  unit/
  integration/
  stress/
  regression/
```

Each layer must be runnable via pytest markers and/or path selection.

### B. Pytest Configuration
Add/extend project pytest config (`pyproject.toml` or `pytest.ini`) to:

- Register markers: `unit`, `fixture`, `integration`, `stress`, `regression`
- Set useful default test paths and options
- Fail on unknown markers

### C. Fixture Contract Enforcement
Implement fixture discovery + validation in `tests/fixture/conftest.py`:

- Auto-discover `case_*` directories.
- Validate required files against `tests/fixture/schemas/case_schema.yaml`.
- Reject missing required files and unexpected files unless explicitly allowed.
- Produce clear errors with actionable paths.

Implement at least a few representative fixture cases (not empty scaffold).

### D. Timeline Invariant Validator
Implement shared validator in `tests/conftest.py` (or helper module) that can be
called by integration/stress tests to enforce global timeline invariants:

1. Ownership shape is valid.
2. Referenced session/job IDs exist in logs metadata.
3. Timeline ordering is valid.
4. Required fields exist for schema/event type.
5. Completed attributed runs contain `root_pid`.

Keep it strict, deterministic, and with clear failure messages.

### E. Unit/Fixture Migration and Coverage Baseline
Migrate or wrap existing collector tests so they run under top-level pytest flow.
Do not reduce coverage. Prefer relocating or importing existing tests over rewrite-only churn.

Minimum expectation:
- Existing collector unit tests are runnable from top-level test entrypoint.
- Fixture tests exist for core filter/summary/merge contracts.

### F. Python Integration Test Layer
Create Python integration tests that replace/cover key current Bash scenarios.
Prioritize critical behavior over full parity in first pass.

At minimum include:
- Job lifecycle artifact validation
- Filter job path behavior
- Merge behavior
- Concurrent sessions/jobs attribution sanity

Use pytest fixtures for:
- unique compose project names per test
- temp logs/work dirs
- unconditional teardown
- artifact collection on failure

### G. Stress Test Layer
Create stress tests with repeatable trial loops.
Implement configurable trial counts via env vars.

Required lanes:
- `stress-smoke`: short deterministic run (PR-safe)
- `stress-full`: larger trial count (nightly/release)

### H. Regression Layer
Create regression test structure and add at least one concrete regression test
for a known historical issue (concurrent attribution bug class).

### I. Canonical Test Runner
Implement one canonical runner for local + CI.

Preferred:
- `scripts/all_tests.py` (Python)

Acceptable:
- `scripts/all_tests.sh` wrapper that delegates mostly to Python

Runner requirements:
- Lane model:
  - `fast`: unit + fixture + regression
  - `pr`: fast + integration + stress-smoke
  - `full`: pr + stress-full
- Deterministic nonzero exits on failure
- Clear summary output
- Ability to run sub-lanes directly

### J. CI Workflows (Required Enforcement)
Add workflows:

1. `.github/workflows/ci-pr.yml`
   - trigger: `pull_request`
   - required jobs:
     - contract/schema checks
     - unit+fixture
     - regression
     - integration
     - stress-smoke

2. `.github/workflows/ci-stress.yml`
   - trigger: nightly schedule + manual dispatch
   - runs stress-full

CI should call the canonical runner (or identical command surface) to avoid drift.

### K. Contract/Delta Enforcement Script
Implement a lightweight enforcement script (Python), e.g.:
- `scripts/verify_test_delta.py` or `scripts/verify_requirements_coverage.py`

It should fail CI for obvious gaps, such as:
- runtime source paths changed with no relevant test changes
- invalid fixture structure
- missing required regression test for flagged bugfix changes (if detectable via labels or commit message convention)

Keep this pragmatic. Avoid fragile deep static analysis in v1.

## 4) Language and Style Requirements
1. ASCII-only unless existing file requires otherwise.
2. Keep code comments concise and high-value.
3. Do not introduce sprawling framework complexity for v1.
4. Prefer explicit assertions with useful diagnostics over clever abstractions.

## 5) Implementation Strategy (Expected Order)
Follow this order:

1. Create pytest config + directory scaffolding.
2. Implement fixture schema + validator + sample fixture cases.
3. Implement global timeline validator helper.
4. Wire existing unit tests into top-level flow.
5. Add Python integration tests with robust fixtures/teardown.
6. Add stress-smoke and stress-full mechanics.
7. Add regression test scaffold + first concrete regression.
8. Add canonical runner with lanes.
9. Add CI workflows and contract/delta check script.
10. Run and stabilize until green.

## 6) Validation and Evidence Required in Final Report
Your final report must include:

1. What files you added/changed.
2. Exact commands you ran.
3. Which lanes passed locally (`fast`, `pr`, `full`, or subset with reason).
4. Known limitations and what is deferred to next iteration.
5. CI check names that should be marked required in branch protection.

If anything could not be run (environment constraint), state that explicitly and
explain what static verification was done instead.

## 7) Practical Guardrails
1. Do not remove existing tests unless replacing with equivalent or better coverage.
2. Do not rely on prebuilt release images when testing branch behavior.
3. Avoid flaky `sleep`-only readiness where robust checks are possible.
4. Ensure every integration test is isolated (unique compose project/resources).
5. Keep failures diagnosable (store logs/artifacts on failure).

## 8) Definition of Done
The work is done when all are true:

1. Top-level pytest architecture exists and is usable.
2. Fixture schema enforcement is active and tested.
3. Timeline validator is implemented and used by integration/stress tests.
4. Canonical lane runner exists and works.
5. CI PR workflow enforces required checks, including stress-smoke.
6. Nightly/manual stress-full workflow exists.
7. At least one meaningful regression test exists.
8. Documentation reflects real runnable commands and matches implementation.

## 9) Stretch Goals (Only After Core Is Green)
1. Port more legacy Bash integration scenarios to Python.
2. Add richer artifact snapshots for failed tests.
3. Expand delta-enforcement accuracy.
4. Add coverage trend reporting if low-effort.

---

Begin implementation now. Prefer shipping a strict, working v1 over an ambitious
but incomplete design.
