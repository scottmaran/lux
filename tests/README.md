# Lasso Test Suite

## Philosophy

The test suite is the specification. If a behavior is not tested, it is not
guaranteed. If a test exists, its name and structure describe exactly what is
promised.

**Guiding principles:**

1. **Interpretability.** Any developer or agent can read the test directory
   tree and understand what Lasso guarantees. Test names are precise
   descriptions of behavior, not implementation details.

2. **Determinism.** Every aspect of the test suite is rigorously defined and
   validated. Test inputs follow defined schemas. Test outputs are compared
   against exact expected values. Fixture case directories have a required
   structure enforced by validation. There is no ambiguity about what a test
   expects, what files a fixture case must contain, or what format they must
   follow. If a convention exists, it is enforced by code

---

## Isolation

Every test is isolated. This is enforced structurally.

- **Unit:** in-memory only, no shared state between functions.
- **Fixture:** each case runs in an independent temp directory.
- **Integration:** fresh temp log dir + unique compose project per test.
- **Stress:** independent resources per trial.
- Teardown is unconditional (runs even on failure).

---

## Running Tests

```bash
pytest tests/unit tests/fixture       # fast, no Docker
pytest tests/integration              # requires Docker
pytest tests/stress                   # requires Docker, slower
pytest                                # everything
pytest -m "not integration and not stress"  # fast gate
```

**Markers:** `unit`, `fixture`, `integration`, `stress`, `regression`.

---

## Structure

```
tests/
  conftest.py             <- shared helpers, timeline validator, structural validation
  pyproject.toml          <- pytest config, marker registration

  unit/                   <- pure logic, no I/O, no Docker
  fixture/                <- deterministic input -> expected output
    conftest.py           <- auto-discovers case_*/ dirs, validates schema
    schemas/
      case_schema.yaml    <- required files and formats per case directory
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
  integration/            <- real Docker stack
    conftest.py           <- compose lifecycle, temp dirs, oracle
  stress/                 <- concurrency, races, repeated trials
  regression/             <- bug-specific, references commit/issue
```

### Unit (`tests/unit/`)

Pure functions, no I/O, no Docker. One test file per source module.
Pattern: `collector/scripts/filter_audit_logs.py` ->
`tests/unit/test_audit_filter.py`.

### Fixture (`tests/fixture/`)

Golden-file tests. Each `case_*/` directory is one test case. Adding a case
requires zero Python — create a directory with the right files and
`conftest.py` picks it up.

**Required files per `case_*/` directory:**

| File | Format | Description |
|------|--------|-------------|
| `README.md` | First line: one-sentence summary | What invariant this case tests |
| `input.log` or `input.jsonl` | Raw log lines or JSONL | Input to the pipeline stage |
| `config.yaml` | YAML | Pipeline config for this case |
| `expected.jsonl` | JSONL | Exact expected output |

`fixture/conftest.py` validates every case directory against
`schemas/case_schema.yaml` before running. Missing or unexpected files fail
with a clear error.

### Integration (`tests/integration/`)

Real Docker stack. Every test gets a fresh temp log directory and unique
compose project name. The timeline validator (see below) runs after any test
that produces a timeline.

### Stress (`tests/stress/`)

Concurrency, PID reuse, race conditions, repeated trials. Each test defines
a trial count and runs the scenario N times. One failure in any trial fails
the test.

### Regression (`tests/regression/`)

One test per bug. Each test references the commit or issue that introduced
the fix. The test must fail if the fix is reverted.

```python
def test_concurrent_sessions_do_not_use_time_window_attribution():
    """Fixed in dcf5673. Time-window attribution caused cross-run leakage."""
    ...
```

---

## Timeline Validator

A validation function in `tests/conftest.py` that checks universal invariants
across all timeline output files. Called after any integration test that
produces a timeline.

**Checks:**
1. Every event has exactly one owner (session xor job).
2. Every referenced session_id/job_id exists on disk.
3. Events are sorted by timestamp.
4. Every event has required fields for its schema_version and event_type.
5. Every completed run with attributed events has a root_pid in metadata.

---

## Conventions

**Test names** describe behavior, not implementation:
```python
def test_shell_lc_flag_extracts_inner_command():
    """bash -lc 'pwd' extracts 'pwd' as the command."""
```

**Fixture dirs** describe the scenario: `case_fs_rename_within_workspace/`,
not `case_1/`.

**Docstrings are mandatory.** The docstring states the invariant.

---

## eBPF Testing

The eBPF kernel program (C/BPF bytecode) runs inside the Docker Desktop VM
kernel and cannot be unit tested on macOS. The Rust loader userspace code
(event parsing, /proc enrichment, JSONL emission) is unit tested with Rust
tests in `collector/ebpf/loader/`. The kernel program is validated through
integration tests that generate known syscall activity and verify captured
output.

---

## Environment

**Unit + fixture:** Python 3.10+, pytest.

**Integration + stress:** above, plus Docker Desktop and Compose v2.
