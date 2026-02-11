# Synthetic Logs In The Test Suite

## Purpose
Synthetic logs exist to keep unit/fixture checks deterministic, fast, and easy
to review.

They are used to validate parsing and schema/shape contracts without depending
on host auditd timing, kernel/eBPF runtime variance, or cross-process timing
noise.

## Current Scope (As Implemented)

### What synthetic data is used for
- Unit tests in `tests/unit/` (especially synthetic fidelity checks).
- Fixture/golden case inputs in `tests/fixture/` (static case files).

### What synthetic data is not used for
- Integration acceptance.
- Stress acceptance.
- Regression acceptance.

Those layers assert behavior from live stack outputs only.

## Current Builders
Builders live in `tests/support/synthetic_logs.py`.

Audit helpers:
- `make_syscall`
- `make_execve`
- `make_cwd`
- `make_path`
- `build_job_fs_sequence`

eBPF helpers:
- `make_net_connect_event`
- `make_net_send_event`
- `make_dns_query_event`
- `make_dns_response_event`
- `make_unix_connect_event`

## Current Validation Coverage
`tests/unit/test_synthetic_log_fidelity.py` currently verifies:

1. Synthetic audit SYSCALL lines include collector-relevant core fields.
2. Synthetic audit lines parse through the real audit parser path.
3. Synthetic eBPF builders for configured event types match real top-level
   shape expectations from `example_logs/ebpf.jsonl`.

Reference real samples:
- `example_logs/audit.log`
- `example_logs/ebpf.jsonl`

## Known Limits
1. Synthetic audit records are still minimal relative to full production
   audit verbosity (`a0..a3`, `auid`, `tty`, `ses`, etc. are not fully modeled).
2. eBPF builder coverage includes required event types, but payload diversity is
   still narrower than production.
3. Most fixture cases use static case files rather than builder-generated inputs.

## Accuracy Standard
Synthetic data is acceptable when all are true:

1. It parses through the same collector code paths as production-form data.
2. It preserves collector-relevant semantics for ownership and event shape.
3. It remains deterministic for CI and local reruns.
4. It does not replace live-stack acceptance in integration/stress/regression.

## Near-Term Improvements
1. Expand audit builder verbosity mode toward production-shape records.
2. Expand eBPF payload variants (protocol/family/result edge cases).
3. Add broader normalized shape comparisons as new real patterns are observed.
4. Keep fixture case coverage and shared builders aligned over time.
