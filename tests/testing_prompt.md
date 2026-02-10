# Lasso Testing Suite Implementation Prompt (Subagent)

You are implementing a full testing suite for Lasso on branch `robust_test_suite`.
This is not a brainstorming task. You are expected to design and ship a strict,
working, end-to-end suite with CI enforcement.

Read this prompt fully before coding. Treat it as the implementation contract.

## 0) Mission
Build a deterministic, comprehensive, maintainable test system such that:

- Passing required gates means no known requirement violations in supported environments.
- The suite is usable identically by local developers and autonomous agents.
- CI enforces behavior and contract boundaries, not just policy text.

Use `tests/README.md` as the authoritative philosophy and behavior contract.

Primary directive for test creation:
- Build tests from scratch against required behaviors/invariants.
- Existing scripts are reference material only.
- Do not treat this as a parity port of legacy Bash tests.

## 1) Critical Interpretation Rules (Read Before Coding)
1. Integration means live end-to-end system behavior:
   - Start the real stack (`collector`, `agent`, `harness`).
   - Submit real jobs through supported interfaces.
   - Assert against live collector outputs and persisted artifacts.
2. Determinism/isolation requirements do not permit bypassing live integration path.
3. Synthetic replay is not a substitute for integration:
   - Unit/fixture may use synthetic inputs.
   - Integration/regression/stress must not rely on offline synthetic pipeline replay for core assertions.
4. Synthetic raw logs must be production-shape:
   - Do not stop at handcrafted minimal valid records.
   - Synthetic records should be as close as practical to real source output.

## 2) Required Context to Read First
Before making changes, read:

1. `tests/README.md`
2. `tests/test_principles.md` (if relevant)
3. `tests/SYNTHETIC_LOGS.md`
4. Collector scripts and tests:
   - `collector/scripts/filter_audit_logs.py`
   - `collector/scripts/filter_ebpf_logs.py`
   - `collector/scripts/summarize_ebpf_logs.py`
   - `collector/scripts/merge_filtered_logs.py`
   - `collector/tests/test_filter.py`
   - `collector/tests/test_ebpf_filter.py`
   - `collector/tests/test_ebpf_summary.py`
   - `collector/tests/test_merge_filtered.py`
5. Existing integration and CLI scripts:
   - `scripts/run_integration_*.sh`
   - `scripts/run_lasso_cli_integration.sh`
   - `scripts/cli_scripts/*`
6. Real log references:
   - `example_logs/audit.log`
   - `example_logs/ebpf.jsonl`
7. Existing workflows:
   - `.github/workflows/release.yml`

Then produce implementation, not analysis.

Important interpretation rule:
- Legacy tests/scripts may be mined for scenario ideas, but design against the
  contract in `tests/README.md` and this prompt.

## 3) Non-Negotiable Constraints
1. Use Python/pytest as the primary test language/orchestration layer.
2. New integration/stress/regression test logic must be Python-based.
3. Use `uv` as Python package manager and runner (`uv sync`, `uv run ...`).
4. Keep one canonical command surface for local + CI.
5. Determinism + isolation are mandatory.
6. Include regression pathway for bug fixes.
7. Enforce via CI + scripts, not docs-only guidance.
8. Integration/regression/stress must validate live stack outputs.
9. Synthetic logs must target high fidelity to real audit/eBPF source data.
10. Agent end-to-end tests must include real Codex execution coverage.

## 4) Deliverables (You Must Implement)

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

Each layer must be runnable by marker and path selection.

### B. Pytest Configuration
Create/extend root `pyproject.toml` as single source of Python test tooling config.
Do not split pytest config unless strictly necessary.

Also generate and commit `uv.lock`.

`pyproject.toml` must:
- Register markers: `unit`, `fixture`, `integration`, `stress`, `regression`
- Set useful default paths/options
- Fail on unknown markers

Tooling requirements:
- CI and local use `uv sync --frozen` before execution.
- Python commands run through `uv run ...`.

### C. Fixture Contract Enforcement
Implement fixture discovery + validation in `tests/fixture/conftest.py`:
- Auto-discover `case_*` directories.
- Validate required files against `tests/fixture/schemas/case_schema.yaml`.
- Reject missing required files and unexpected files unless explicitly allowed.
- Produce clear, actionable errors.

Implement representative fixture cases (not empty scaffolding).

### D. Timeline Invariant Validator
Implement shared validator in `tests/conftest.py` (or helper module) for
timeline-producing tests:
1. Ownership shape is valid.
2. Referenced session/job IDs exist in metadata.
3. Timeline ordering is valid.
4. Required fields exist for schema/event type.
5. Completed attributed runs contain `root_pid`.

Keep it strict, deterministic, and diagnosable.

### E. Unit/Fixture Coverage Baseline
Build clean top-level unit/fixture suites satisfying the contract.
Reuse existing test code only if it is correct and high quality.

Minimum expectation:
- Core collector logic covered from top-level entrypoint.
- Fixture tests for core filter/summary/merge contracts.

### F. Integration Layer (Live End-to-End, Required)
Create Python integration tests for contract-critical behaviors.

Required execution model:
- Bring up real compose stack.
- Submit real jobs through harness API/CLI path used by users.
- Wait for completion via API polling.
- Assert on artifacts and collector outputs produced by the running stack.

Required assertion sources:
- `/logs/jobs/<job_id>/*` metadata/artifacts
- live `filtered_audit.jsonl`
- live `filtered_ebpf.jsonl`
- live `filtered_timeline.jsonl`

At minimum include:
- Job lifecycle artifact validation
- Filesystem action from submitted job appears with correct ownership/attribution
- Network action from submitted job appears with correct ownership/attribution
- Merge/timeline invariants over live collected output
- Concurrent jobs/sessions attribution sanity

Explicitly prohibited in integration assertions:
- Running collector scripts directly on synthetic inputs to stand in for live behavior
- Treating offline replay as acceptance evidence for integration behavior

Use pytest fixtures for:
- unique compose project names per test
- temp logs/work dirs
- unconditional teardown
- artifact/log capture on failure

### G. Agent E2E Contract (Codex Required)
In addition to generic integration tests, implement explicit agent user-flow tests
that exercise Codex through the running harness/agent stack.

Required Codex lanes:
- `agent-codex-exec`:
  - Use Codex non-interactive command path (for example `codex exec ...`).
  - Submit a realistic user prompt via `/run`.
  - Assert job completion, exit code, stdout presence, and expected filtered timeline ownership.
- `agent-codex-tui`:
  - Use Codex interactive/TUI launch path through harness TTY plumbing.
  - Simulate user input/actions through the supported TUI path.
  - Assert command/session completion, captured artifacts, and expected filtered timeline ownership.

Both Codex lanes must verify behavior, not just startup:
- containers healthy,
- Codex command actually ran,
- output is non-empty and non-error for success scenarios,
- failure scenarios produce expected error classification.

Implementation requirements:
- run against live stack (no offline replay),
- include failure diagnostics (stdout/stderr, harness/agent logs, timeline excerpt),
- do not implement these Codex lanes with `bash -lc {prompt}` template.

Environment/CI policy:
- GitHub CI does not have Codex credentials; do not make Codex lanes required CI jobs there.
- Codex lanes (`exec` + `tui`) must run locally in credentialed environments and be treated as required for release confidence.

### H. Stress Layer (Live Stack, Repeatability)
Create stress tests with repeatable trial loops and configurable trial counts.

Required lanes:
- `stress-smoke`: short deterministic run (PR-safe)
- `stress-full`: larger trial count (nightly/release)

Stress scenarios must execute against live stack behavior, not offline replay.

### I. Regression Layer
Create regression structure and at least one concrete regression test for a known
historical issue (concurrent attribution bug class).

If the bug was integration-visible, regression should reproduce and assert through
live stack path.

### J. Synthetic Log Fidelity Program
Implement a deliberate synthetic fidelity track for unit/fixture layers.

Requirements:
- Synthetic builders generate raw records close to real source shape.
- Do not stop at minimally valid handcrafted lines.
- Cover configured eBPF event types (`net_connect`, `net_send`, `dns_query`,
  `dns_response`, `unix_connect`) with reusable builders.
- Add fidelity tests comparing normalized synthetic-vs-real structure using:
  - `example_logs/audit.log`
  - `example_logs/ebpf.jsonl`
- Normalize volatile fields (timestamps, PIDs, seq IDs, inode-like IDs) before comparison.
- Document intentionally omitted fields in `tests/SYNTHETIC_LOGS.md` with rationale.

### K. Canonical Test Runner
Implement one canonical runner for local + CI.

Required:
- `scripts/all_tests.py` (Python)

Optional:
- `scripts/all_tests.sh` as thin wrapper calling `scripts/all_tests.py`

Runner requirements:
- Lane model:
  - `fast`: unit + fixture + regression
  - `pr`: fast + integration + stress-smoke
  - `full`: pr + stress-full
- Deterministic nonzero exits on failure
- Clear summary output
- Ability to run sub-lanes directly
- Use `uv run` for Python tools/tests in all lanes

Required local lanes must include:
- `agent-codex-exec`
- `agent-codex-tui`

### L. CI Workflows (Required Enforcement)
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

CI should call canonical runner (or identical command surface) to avoid drift.
CI Python setup must run `uv sync --frozen`.

### M. Contract/Delta Enforcement Script
Implement lightweight enforcement script (Python), e.g.:
- `scripts/verify_test_delta.py` or `scripts/verify_requirements_coverage.py`

It should fail CI for obvious gaps:
- runtime source changed without relevant tests
- invalid fixture structure
- missing required regression change for bug-fix changes

Bug-fix enforcement must be deterministic:
- Add `--change-kind {feature,fix,refactor}`
- If `change-kind=fix`, require changed file under `tests/regression/`
- CI must pass `change-kind` explicitly

Add one boundary guard for architecture drift:
- Fail if `tests/integration/`, `tests/stress/`, or `tests/regression/` uses
  disallowed offline synthetic replay helpers for core assertions.
- Fail if Codex-designated agent-e2e tests use `HARNESS_RUN_CMD_TEMPLATE=bash -lc {prompt}`.
- Fail if required Codex lanes (`agent-codex-exec`, `agent-codex-tui`) are missing.

Keep this pragmatic. Avoid fragile deep static analysis in v1.

## 5) Language and Style Requirements
1. ASCII-only unless existing file requires otherwise.
2. Keep comments concise and high-value.
3. Avoid sprawling framework complexity for v1.
4. Prefer explicit assertions with useful diagnostics.

## 6) Implementation Strategy (Expected Order)
Follow this order:

1. Create pytest config + directory scaffolding.
2. Implement fixture schema + validator + sample fixture cases.
3. Implement shared timeline validator.
4. Implement unit baseline for collector logic.
5. Implement live end-to-end integration tests against running stack outputs.
6. Implement Codex agent-e2e lanes (`exec` and `tui`) with success + expected-failure assertions.
7. Implement live-stack stress and regression flows.
8. Implement synthetic fidelity builders + parity tests for unit/fixture usage.
9. Add canonical runner with lanes.
10. Add CI workflows + contract/delta enforcement guards.
11. Run and stabilize until green.

## 7) Validation and Evidence Required in Final Report
Final report must include:

1. Files added/changed.
2. Exact commands run.
3. Which lanes passed locally (`fast`, `pr`, `full`, or subset with reason).
4. Known limitations and deferred items.
5. CI check names to mark required in branch protection.
6. Evidence that integration assertions came from live stack outputs.
7. Evidence synthetic fidelity tests passed and what was normalized.
8. Evidence Codex `exec` and `tui` lanes executed, including success and expected-failure outcomes.

If anything could not be run, state it explicitly and explain static verification.

All Python commands in report must use `uv` (for example `uv run pytest ...`).

## 8) Practical Guardrails
1. Do not remove existing tests unless replaced with equivalent or better coverage.
2. Do not rely on prebuilt release images for branch behavior tests.
3. Avoid flaky sleep-only readiness where robust checks are possible.
4. Ensure every integration/stress/regression test is isolated.
5. Keep failures diagnosable with captured logs/artifacts.
6. If integration behavior can only pass through offline replay, treat as a test design failure and fix architecture.

## 9) Definition of Done
Work is done when all are true:

1. Top-level pytest architecture exists and is usable.
2. Fixture schema enforcement is active and tested.
3. Timeline validator is implemented and used by timeline-producing tests.
4. Canonical lane runner exists and works.
5. CI PR workflow enforces required checks including stress-smoke.
6. Nightly/manual stress-full workflow exists.
7. At least one meaningful regression test exists.
8. Integration tests assert live stack outputs for lifecycle, fs, net, merge, and concurrency behaviors.
9. Synthetic fidelity program exists with parity tests against real log references.
10. Codex agent-e2e lanes (`exec` and `tui`) are implemented and passing in required environments.
11. Documentation matches real runnable commands and implemented behavior.

## 10) Stretch Goals (Only After Core Is Green)
1. Decommission remaining legacy Bash test scripts after equivalent/better Python coverage exists.
2. Add richer artifact snapshots for failed tests.
3. Expand delta-enforcement accuracy.
4. Add coverage trend reporting if low-effort.

---

Begin implementation now. Prefer shipping a strict, working v1 over an ambitious
but incomplete design.
