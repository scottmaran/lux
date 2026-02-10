# Synthetic Logs In The Test Suite

## Purpose

Synthetic logs exist to make collector testing deterministic, fast, and reviewable.

They let us test attribution/filter/summary/merge behavior without depending on:
- host auditd timing and log noise,
- kernel/eBPF runtime variance,
- flaky race windows in asynchronous pipelines.

They are not meant to perfectly reproduce every raw kernel field by default. They are meant to reproduce the fields and structure that the collector logic actually consumes, while still being close enough to production formats to catch real regressions.

## Current Sources

- Audit synthetic builders live in `tests/support/synthetic_logs.py`:
  - `make_syscall`
  - `make_execve`
  - `make_cwd`
  - `make_path`
  - `build_job_fs_sequence`
- eBPF synthetic builder currently in `tests/support/synthetic_logs.py`:
  - `make_net_send_event`

## How Synthetic Logs Are Used Today

### Integration/Regression/Stress

- `tests/support/integration_stack.py` uses `run_collector_pipeline(...)` to run the real collector scripts against synthetic inputs:
  - `filter_audit_logs.py`
  - `filter_ebpf_logs.py`
  - `summarize_ebpf_logs.py`
  - `merge_filtered_logs.py`
- Integration/regression/stress scenarios primarily use:
  - synthetic audit sequences (`build_job_fs_sequence`) for ownership + filesystem attribution,
  - optional synthetic eBPF `net_send` events for network summary/merge validation.

### Fixture Layer

- The fixture suite validates stage contracts using static synthetic JSONL/log samples:
  - audit filter fixtures,
  - eBPF filter fixtures (`net_connect` currently covered),
  - eBPF summary fixtures (`dns_response` + `net_send` covered),
  - merge fixtures,
  - end-to-end pipeline fixtures.

This means eBPF type breadth exists in fixture data, but not yet fully in reusable Python builders.

## Why Real Audit Logs Look More Verbose

Real auditd SYSCALL entries include many low-level fields (`a0..a3`, `auid`, `euid`, `tty`, `ses`, etc.). Our synthetic SYSCALL lines are currently minimal and include the subset consumed by the collector parser and event-building logic.

This is intentional for readability/determinism, but we should improve fidelity so synthetic inputs better mirror production raw shape.

## Current Position (Explicit)

For integration/regression/stress, `build_job_fs_sequence` generates **synthetic raw audit logs** that are:
- minimally viable for parser + attribution/filter logic,
- intentionally cleaner/shorter than full production audit output.

These are **not** filtered audit logs. They are raw synthetic inputs that are then passed through the real collector filtering scripts during tests.

This is acceptable for now as a deterministic baseline.

## Near-Term Direction

Near-term target is to move from minimal synthetic raw logs to **fully verbose, production-shape synthetic logs** that are as close as possible to real audit/eBPF output while preserving determinism.

Concretely, we should:
- expand raw audit builders to emit the full expected field surface used in real logs,
- expand eBPF builders to cover all configured event types and realistic payload variants,
- validate synthetic-vs-real structural parity with automated tests against representative real samples.

## Gaps To Address

- Builder coverage gap on eBPF side:
  - only `net_send` helper exists in Python builders today.
- Raw-field fidelity gap:
  - audit synthetic records are structurally valid but less verbose than production logs.
- Consistency gap:
  - richer eBPF event coverage lives in fixture JSONL files, not shared builders.
- Verification gap:
  - no dedicated automated “synthetic vs real shape” parity test module yet.

## Improvement Plan (Priority Order)

1. Expand eBPF builders in `tests/support/synthetic_logs.py`:
   - `make_net_connect_event`
   - `make_dns_query_event`
   - `make_dns_response_event`
   - `make_unix_connect_event`
2. Add higher-fidelity audit builder mode:
   - include optional extended SYSCALL fields (`a0..a3`, `items`, `auid`, `euid`, `tty`, `ses`, etc.),
   - keep defaults deterministic and easy to read.
3. Add synthetic fidelity tests:
   - parser acceptance tests against generated records,
   - normalized real-vs-synthetic shape comparisons using `example_logs/audit.log` and `example_logs/ebpf.jsonl`.
4. Increase integration coverage using builders:
   - at least one integration scenario per major eBPF `event_type` in config include list.
5. Keep fixtures and builders aligned:
   - when adding a new event type to fixture cases, add/maintain corresponding builder helper.

## Practical Accuracy Standard

Synthetic logs should satisfy all of the following:
- parse cleanly through the same collector code paths as production logs,
- preserve collector-relevant field semantics and ownership/linking behavior,
- represent key production patterns (success/failure exec, filesystem events, network variants),
- remain deterministic and concise enough for debugging and CI stability.

## Next Additions We Should Make

- Add missing eBPF helper constructors listed above.
- Add one dedicated unit module for synthetic fidelity checks.
- Add at least one integration test that uses each new eBPF helper.
- Document any intentionally omitted raw fields and why they are omitted.
