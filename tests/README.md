# Lasso Test Suite

## Why This Exists
The test suite is the specification for observable Lasso behavior.

Passing the suite means:
- No known requirement violations in the supported environments.
- Known bug regressions are blocked.
- Artifacts and attribution invariants hold.

This does not claim mathematical proof of correctness. It claims release confidence within defined scope.

## Scope and Environments
Supported environments:
- macOS with Docker Desktop
- Linux with Docker and Compose v2

In scope:
- Collector pipeline correctness (audit/eBPF filter, summarize, merge)
- Harness job/session lifecycle behavior
- Timeline ownership and schema invariants
- Regression protection for previously fixed bugs
- Local agent end-to-end validation through Codex (`exec` and interactive TUI)

Out of scope:
- Throughput benchmarking and performance tuning
- Agent model quality
- Host tamper-resistance guarantees outside Lasso's trust model

## Non-Negotiable Properties
1. Determinism: tests compare against explicit expected outcomes.
2. Isolation: every test run uses independent resources.
3. Reproducibility: reruns in the same environment produce the same verdict.
4. Explicit invariants: each test states what must always be true.
5. No silent ambiguity: ambiguous ownership must fail or be marked unknown by rule.

## Test Layers
| Layer | Purpose | Must Include | Must Not Include | Typical Runtime |
|---|---|---|---|---|
| `unit` | Pure logic correctness | Parsing, mapping, ownership logic, validation helpers | Docker, real stack orchestration | Seconds |
| `fixture` | Deterministic contract checks | Golden cases (`input` + `config` -> `expected`) | Ad-hoc assertions without canonical expected output | Seconds |
| `integration` | Real stack behavior | Docker compose scenarios, real artifact validation, live filtered output assertions, CLI script compatibility coverage | Offline synthetic replay as acceptance evidence | Minutes |
| `stress` | Concurrency and race robustness | Repeated trials, overlap/race/PID reuse scenarios | New feature coverage without deterministic baseline tests | Minutes to longer |
| `regression` | Bug non-recurrence | Repro of known bug condition + assertion of fixed behavior | Generic tests not tied to a concrete bug history | Varies |

## Directory Contract
```text
tests/
  README.md                    <- this file
  conftest.py                  <- shared fixtures and validators
  unit/                        <- pure logic tests
  fixture/                     <- deterministic golden cases
    conftest.py                <- fixture discovery and schema validation
    schemas/
      case_schema.yaml         <- fixture directory schema
    audit_filter/
      case_*/
    ebpf_filter/
      case_*/
    summary/
      case_*/
    merge/
      case_*/
    pipeline/
      case_*/
  integration/
    compose.test.override.yml    <- test-only compose deltas layered onto `compose.yml`
    config/                    <- test-only collector filter config overrides for compose
                                (keeps CI-safe bash attribution without changing prod defaults)
    test_*.py                  <- real Docker stack tests
                                includes `test_cli_script_suite.py` which executes
                                `scripts/cli_scripts/*.sh` inside pytest
  stress/                      <- race/concurrency repetition tests
  regression/                  <- bug-specific tests
```

## Fixture Case Schema
Each `case_*/` directory is one deterministic test case and must contain:

| File | Format | Required | Purpose |
|---|---|---|---|
| `README.md` | Markdown | Yes | Human-readable invariant summary |
| `config.yaml` | YAML | Yes | Configuration used by this case |
| `expected.jsonl` | JSONL | Yes | Canonical expected output |
| `input.log` or `input.jsonl` | Log/JSONL | Yes | Canonical input |

Schema rules:
- Unknown files are rejected unless explicitly allowed by schema.
- Missing required files fail fixture validation.
- Case directories are discovered automatically by pattern `case_*`.

## Global Invariant Validator
Any test that produces timeline output must run a shared validator that enforces:
1. Ownership shape: each event has one valid owner pattern.
2. Referential integrity: referenced session/job IDs exist in run metadata.
3. Ordering: timeline timestamps are non-decreasing.
4. Required fields: event has required keys for `schema_version` and `event_type`.
5. Root marker completeness: attributed completed runs include persisted `root_pid` and `root_sid`.

Attribution note:
- Collector attribution is PID-lineage first, with `root_sid` fallback when PID lineage is temporarily unavailable during startup/concurrency windows.

## Change Protocol (For PRs and Agents)
When code changes, test updates are mandatory and deterministic.

| Source Change Area | Required Test Action |
|---|---|
| `collector/scripts/*.py` | Update corresponding `tests/unit/test_*.py`; add/update fixture cases for changed contracts |
| `collector/config/*.yaml` | Update fixture cases affected by config semantics |
| `collector/ebpf/loader/**` | Update Rust unit tests; update fixture/integration tests if emitted shape changes |
| `collector/ebpf/ebpf/**` | Add/update integration or stress tests that exercise the syscall path |
| `harness/**` | Add/update harness unit tests; integration tests for lifecycle-visible behavior changes |
| `ui/server.py` or API code | Add/update API unit tests and integration checks for externally visible behavior |
| `compose*.yml` or Dockerfiles | Add/update integration coverage for startup/networking/artifact expectations |
| Any bug fix | Add regression test that fails without the fix |

Protocol:
1. Implement source change.
2. Update required tests from mapping above.
3. Run required gates.
4. Do not open merge PR until all required gates pass.

## Running the Suite
Canonical local commands:

```bash
uv sync

# Fast local gate
uv run pytest tests/unit tests/fixture -q

# Integration gate
uv run pytest tests/integration -m "integration and not agent_codex and not agent_claude" -q

# Local-only Codex agent E2E gates (requires ~/.codex auth + skills)
uv run pytest tests/integration -m agent_codex -q

# Local-only Claude agent E2E gates
uv run pytest tests/integration -m agent_claude -q

# Stress gate
uv run pytest tests/stress -q

# Regression gate
uv run pytest tests/regression -q

# Full gate
uv run pytest -q
```

Integration gate note:
- `tests/integration/test_cli_script_suite.py` runs the shell CLI suite under
  pytest and requires `script(1)` for TUI smoke coverage.
- Local Codex coverage includes `tests/integration/test_agent_codex_cli_tui.py`,
  which validates interactive Codex behavior through `lasso tui --provider codex`.

Marker-based selection:

```bash
uv run pytest -m unit -q
uv run pytest -m fixture -q
uv run pytest -m integration -q
uv run pytest -m "integration and not agent_codex and not agent_claude" -q
uv run pytest -m agent_codex -q
uv run pytest -m agent_claude -q
uv run pytest -m stress -q
uv run pytest -m regression -q
uv run pytest -m "not integration and not stress" -q
```

`scripts/all_tests.py` is the canonical release gate entrypoint.
If `scripts/all_tests.sh` exists, it should only be a thin wrapper around `scripts/all_tests.py`.

Canonical lane examples:

```bash
# CI-safe lanes
uv run python scripts/all_tests.py --lane fast
uv run python scripts/all_tests.py --lane pr
uv run python scripts/all_tests.py --lane full

# Local-only Codex lane
uv run python scripts/all_tests.py --lane codex
uv run python scripts/all_tests.py --lane claude

# Local comprehensive lane (CI-safe + Codex)
uv run python scripts/all_tests.py --lane local-full
```

## CI and Merge Gates
Required gates for protected branches:
1. Fixture schema validation
2. Unit + fixture tests
3. Integration tests
4. Regression tests
5. Stress-smoke tests
6. Any repository-specific static checks

Codex policy:
- Codex `exec` + interactive TUI agent-e2e tests are required for local release confidence.
- They are not required in GitHub CI because credentials are unavailable there.

Stress-full policy:
- Required for nightly runs.
- Required before release cut.

No bypass rule:
- A failing required gate blocks merge.
- If a gate is flaky, fix the test infrastructure; do not disable silently.

## Naming and Style Conventions
Test function rules:
- Name behavior, not implementation detail.
- Include a docstring that states the invariant being proven.

Examples:
```python
def test_shell_lc_extracts_inner_command():
    """bash -lc wraps command text; extractor returns inner command verbatim."""
```

Fixture naming:
- Use descriptive directory names: `case_fs_rename_within_workspace`.
- Avoid numeric names like `case_1`.

Regression naming:
- Name after the bug condition, not the patch mechanism.
- Include commit or issue reference in docstring.

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---|---|---|
| Integration tests time out | Docker daemon not ready or containers unhealthy | Check Docker status and compose logs; rerun after health is green |
| Fixture validation fails | Missing/unexpected files in `case_*` directory | Fix case contents to match schema |
| Timeline invariant fails | Ownership/ordering/reference bug in filter or merge pipeline | Inspect generated timeline and run metadata, then patch logic |
| Regression test fails after refactor | Bug condition reintroduced | Reproduce with failing regression and fix behavior, not the test expectation |
| Nondeterministic pass/fail | Hidden shared state or timing race | Isolate resources per test and remove wall-clock assumptions |
