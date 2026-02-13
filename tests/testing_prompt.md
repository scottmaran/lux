# Lasso Testing Suite Implementation Prompt (Subagent)

You are implementing the Lasso test suite on branch `robust_test_suite`.
This is an implementation task, not a design discussion.
Ship a strict, runnable suite with enforceable CI behavior.

Read this file fully before coding. Treat it as the implementation contract.

## 0) Mission
Build a deterministic, maintainable, end-to-end test system where:

- Required gates map to real requirements, not placeholder checks.
- Local developers and agents can run the same canonical commands.
- CI enforces behavior and contract boundaries, not documentation-only rules.

Use `tests/README.md` as the test philosophy source of truth.

Primary directive:
- Create tests from scratch against required behavior and invariants.
- Existing scripts/tests are reference material only.
- Do not treat this task as a parity port of legacy Bash tests.

## 1) Critical Interpretation Rules
1. Integration means live stack behavior.
   - Start real services (`collector`, `agent`, `harness`) with compose.
   - Drive real user-facing entrypoints.
   - Assert on live outputs and persisted artifacts.
2. Determinism/isolation do not permit replacing live integration with replay.
3. Synthetic replay is only for unit/fixture contract testing.
   - Integration/regression/stress must not use offline replay as core evidence.
4. Synthetic raw logs must be production-shape.
   - Do not stop at handcrafted minimal lines.
   - Keep synthetic structures close to real source output.
5. Agent TUI validation must prove interactive behavior, not only TTY/plumbing.

## 2) Required Context to Read First
Read these files before editing:

1. `tests/README.md`
2. `tests/test_principles.md` (if present/relevant)
3. `tests/SYNTHETIC_LOGS.md`
4. `collector/scripts/filter_audit_logs.py`
5. `collector/scripts/filter_ebpf_logs.py`
6. `collector/scripts/summarize_ebpf_logs.py`
7. `collector/scripts/merge_filtered_logs.py`
8. `collector/tests/test_filter.py`
9. `collector/tests/test_ebpf_filter.py`
10. `collector/tests/test_ebpf_summary.py`
11. `collector/tests/test_merge_filtered.py`
12. `tests/integration/test_*.py`
13. `tests/support/integration_stack.py`
14. `tests/support/pytest_docker.py`
15. `compose.yml`
16. `tests/integration/compose.test.override.yml`
17. `compose.codex.yml`
18. `tests/unit/test_compose_contract_parity.py`
19. `scripts/all_tests.py`
20. `scripts/verify_test_delta.py`
21. `install_lasso.sh` and `tests/integration/test_cli_*.py` (installer/update/uninstall and CLI lifecycle coverage)
22. `example_logs/audit.log`
23. `example_logs/ebpf.jsonl`
24. `.github/workflows/release.yml`

Then implement. Do not stop at analysis.

## 3) Non-Negotiable Constraints
1. Python + pytest are the primary test/orchestration language.
2. New integration/regression/stress logic must be Python-based.
3. Use `uv` for dependency and command execution (`uv sync`, `uv run ...`).
4. Maintain one canonical local+CI runner surface.
5. Enforce invariants in code/CI scripts, not only in prose.
6. Integration/regression/stress assertions must come from live stack outputs.
7. Add regression coverage for bug-fix class changes.
8. Include explicit Codex agent coverage (`exec` and interactive `tui`).
9. Integration compose must layer on shipping `compose.yml` with minimal
   test-only overrides; do not maintain a copied test stack file.
10. Compose parity must be enforced in tests for service/env/volume contracts
    and allowlisted override deltas.

## 4) Required Deliverables

### A) Test Directory Structure
Create or standardize:

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

Each layer must be runnable by marker and by path.

### B) Pytest + uv Configuration
Use root `pyproject.toml` as single source for pytest tool config.
Generate and commit `uv.lock`.

Requirements:
- markers: `unit`, `fixture`, `integration`, `stress`, `regression`, `agent_codex`
- fail on unknown markers
- sane defaults for diagnostics
- CI and local commands run via `uv run ...`
- CI setup uses `uv sync --frozen`

### C) Fixture Contract Enforcement
Implement fixture discovery and schema validation in `tests/fixture/conftest.py`.

Required behavior:
- auto-discover `case_*` directories
- validate required files via `tests/fixture/schemas/case_schema.yaml`
- reject missing required files
- reject unexpected files unless explicitly allowed
- emit actionable errors

Add representative fixture cases (not empty scaffolding).

### D) Shared Timeline Invariant Validator
Implement strict shared validator in `tests/conftest.py` (or helper module).
It must enforce:

1. ownership shape validity
2. referenced session/job IDs exist
3. timeline ordering validity
4. required field presence by schema/event
5. `root_pid` presence for completed attributed runs

Must be deterministic and diagnosable.

### E) Unit + Fixture Baseline
Implement top-level unit and fixture suites from branch behavior requirements.
Reuse existing tests only if correct and maintainable.

Minimum:
- collector core logic covered via top-level entry behavior
- fixture tests for filter/summary/merge contracts

### E2) Compose Topology + Parity Contract
Integration stack wiring must use:

- base: `compose.yml`
- test override: `tests/integration/compose.test.override.yml`
- codex override (codex lanes): `compose.codex.yml`

Requirements:
- no standalone copied integration stack file (e.g. `compose.stack.yml` clones)
- test override must contain only test-only deltas (local build/image wiring,
  collector test-config mount/env, no broad runtime contract rewrites)
- harness host port must be parameterized for isolated tests (`HARNESS_HOST_PORT`)
- add/maintain compose parity tests that assert:
  - required runtime contracts in base compose
  - override allowlist boundaries
  - codex override remains scoped to expected mounts only

### F) Integration Layer (Live End-to-End)
Create integration tests that:

- start real compose stack
- submit real jobs through supported harness API/CLI user paths
- wait for completion via polling/status
- assert live outputs and artifacts from running stack

Compose rule:
- integration stack must be composed from `compose.yml` + test override
  (and codex override where applicable), not from a copied compose definition.

Required assertion sources:
- `/logs/jobs/<job_id>/*`
- `filtered_audit.jsonl`
- `filtered_ebpf.jsonl`
- `filtered_timeline.jsonl`

Minimum integration behavior coverage:
- job lifecycle artifact validation
- filesystem action attribution
- network action attribution
- merged timeline invariants
- concurrent job/session attribution sanity

Explicitly prohibited:
- using offline synthetic replay as acceptance evidence for integration behavior

### G) Agent End-to-End Contract (Codex Required)
Implement explicit agent user-flow tests against live stack.

Required lanes:

1. `agent-codex-exec`
   - use non-interactive Codex command path (`codex exec ...`)
   - submit realistic user prompt through `/run`
   - assert completion, exit code, stdout presence, ownership evidence in timeline

2. `agent-codex-tui-interactive` (strict interactive requirement)
   - use harness TUI launch path (`harness.py tui`)
   - launch Codex TUI (no `codex exec`)
   - provide prompt via interactive stdin after TUI startup
   - assert actual command execution from interactive input

Interactive TUI required test set:

- `agent-codex-tui-smoke`
  - single session prompt asks Codex to run `pwd`
  - assert session-owned timeline `exec` row contains `pwd`
  - assert stdout includes `/work` (or expected working dir)

- `agent-codex-tui-concurrent`
  - two TUI sessions active concurrently with different prompts
  - assert distinct session IDs and overlapping session windows
  - assert each lane has prompt-related output and independent evidence

Required TUI evidence (must be produced in tests, not only report text):

1. Session metadata: mode `tui`, valid `root_pid`, completion or controlled stop state.
2. Input evidence: `stdin.log` (or equivalent capture) includes typed prompt content.
3. Output evidence: `stdout.log` contains prompt-related non-error content.
4. Behavior evidence: timeline has session-owned `exec` rows proving prompted actions.

TUI completion handling requirement:
- implement robust completion/quiescence logic that ignores heartbeat-like noise.
- avoid pure fixed sleeps.
- collect diagnostics on timeout/failure (stdout/stderr/timeline excerpt).

### H) Stress Layer (Live Stack)
Implement repeatable stress tests with configurable trial counts.

Required lanes:
- `stress-smoke` (PR-safe)
- `stress-full` (nightly/release)

Stress must run against live stack behavior, not offline replay.

### I) Regression Layer
Create regression structure and at least one concrete regression test for known
concurrent attribution bug class.

If bug was integration-visible, regression must assert through live stack path.

### J) Synthetic Fidelity Program
Implement synthetic builders for unit/fixture layers with high fidelity to source logs.

Requirements:
- raw synthetic records near real audit/eBPF source shapes
- include reusable eBPF builders for:
  - `net_connect`
  - `net_send`
  - `dns_query`
  - `dns_response`
  - `unix_connect`
- add synthetic-vs-real structure tests using:
  - `example_logs/audit.log`
  - `example_logs/ebpf.jsonl`
- normalize volatile fields before comparison (timestamps, pids, seq ids, inode-like ids)
- document omissions/tradeoffs in `tests/SYNTHETIC_LOGS.md`

### K) Canonical Test Runner
Implement one canonical runner:

- required: `scripts/all_tests.py`
- optional: thin shell wrapper calling Python runner

Runner lanes:
- `fast`: unit + fixture + regression
- `pr`: fast + integration + stress-smoke
- `full`: pr + stress-full
- `codex`: `agent-codex-exec` + `agent-codex-tui-interactive`

Runner requirements:
- deterministic nonzero exit on failure
- clear lane summary output
- run sub-lanes directly
- use `uv run` everywhere

### L) CI Workflows
Add workflows:

1. `.github/workflows/ci-pr.yml`
   - trigger: `pull_request`
   - required checks:
     - contract/schema checks
     - unit+fixture
     - regression
     - integration
     - stress-smoke

2. `.github/workflows/ci-stress.yml`
   - trigger: nightly schedule + manual dispatch
   - runs stress-full

CI must call canonical runner (or exact equivalent commands).
CI must use `uv sync --frozen`.

Codex credential policy:
- GitHub CI lacks Codex creds, so Codex lanes are not required CI checks there.
- Codex lanes are required for local release confidence.

### M) Contract/Delta Enforcement Script
Implement enforcement script, for example:
- `scripts/verify_test_delta.py` or `scripts/verify_requirements_coverage.py`

Must fail CI for obvious gaps:
- runtime source changed without relevant tests
- invalid fixture structure
- missing regression update for fix-class change

Must support deterministic fix gating:
- `--change-kind {feature,fix,refactor}`
- when `change-kind=fix`, require changes under `tests/regression/`

Required architecture guards:
- fail if integration/stress/regression core assertions depend on offline replay helpers
- fail if Codex tests use forbidden template `HARNESS_RUN_CMD_TEMPLATE=bash -lc {prompt}`
- fail if required Codex lanes are missing
- fail if a copied integration compose stack file is introduced instead of
  base + override layering
- fail if compose parity contract tests are missing from the unit suite

Required TUI guard:
- fail if tests marked as interactive TUI do not send stdin after startup
- fail if interactive TUI tests do not assert session-owned `exec` evidence

Keep v1 pragmatic. Avoid fragile deep static analysis.

## 5) Explicitly Prohibited Anti-Patterns
1. Declaring TUI success based only on container health or process start.
2. Treating "TUI path launched" as equivalent to interactive agent behavior.
3. Implementing TUI lane with `codex exec`.
4. Passing full prompt on command line and claiming interactive behavior without stdin-driven evidence.
5. Integration acceptance via offline replay.
6. Silencing flaky tests instead of fixing readiness/isolation.
7. Copying `compose.yml` into a separate integration stack and allowing drift.

## 6) Implementation Order
1. pytest config + directory scaffolding
2. fixture schema validation + representative cases
3. compose base+override wiring + parity contract tests
4. unit baseline
5. live integration suite
6. Codex lanes (`exec`, `tui-smoke`, `tui-concurrent`) with strict interactive evidence
7. stress and regression layers
8. synthetic fidelity builders + parity tests
9. canonical runner
10. CI workflows + delta/enforcement script
11. stabilize and rerun until green

## 7) Final Report Requirements
Final report must include:

1. files added/changed
2. exact commands run
3. lane outcomes (`fast`, `pr`, `full`, `codex`, or subset with reason)
4. known limitations/deferred items
5. CI check names for branch protection
6. evidence integration assertions came from live stack outputs
7. evidence synthetic fidelity tests passed and what was normalized
8. evidence Codex lanes executed

For `agent-codex-tui-interactive`, include explicit evidence lines:
- session id and session meta summary
- stdin evidence snippet proving prompt was typed via TUI input path
- timeline row excerpt proving session-owned `exec` from that interaction
- stdout evidence snippet showing non-error prompt-related result

If anything was not run, say so explicitly and provide static verification details.

All Python commands in report must use `uv`.

## 8) Practical Guardrails
1. Do not delete existing tests unless replaced with equal or better coverage.
2. Do not rely on release images for branch behavior validation.
3. Use robust readiness checks, not sleep-only coordination.
4. Keep integration/stress/regression isolated per test run.
5. Capture logs/artifacts on failure for diagnosis.
6. If required behavior cannot be proven via live path, treat test design as incomplete and fix it.

## 9) Definition of Done
Done means all are true:

1. top-level pytest architecture exists and is usable
2. fixture schema enforcement is active and tested
3. timeline validator exists and is used where required
4. canonical lane runner exists and works
5. PR CI workflow enforces required checks including stress-smoke
6. nightly/manual stress-full workflow exists
7. at least one meaningful regression test exists
8. integration tests validate live stack outputs for lifecycle/fs/net/merge/concurrency
9. synthetic fidelity program exists with real-log parity tests
10. Codex `exec` lane passes in credentialed environment
11. Codex interactive TUI lanes prove stdin-driven behavior and session-owned execution evidence
12. compose parity tests enforce base runtime contracts + override boundaries
13. docs and commands match real implementation

## 10) Stretch Goals (Only After Core Green)
1. decommission legacy Bash tests after equivalent Python coverage exists
2. richer failure artifact snapshots
3. improved delta-enforcement precision
4. lightweight coverage trend reporting

---

Begin implementation now. Ship strict, working v1 behavior coverage.
