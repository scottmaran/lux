# Synthetic Log Fidelity Program

Synthetic logs in `tests/support/synthetic_logs.py` are intentionally shaped to
match real collector inputs while keeping deterministic values for testing.

## Scope

Synthetic builders cover these eBPF event types:

- `net_connect`
- `net_send`
- `dns_query`
- `dns_response`
- `unix_connect`

Synthetic raw audit helpers cover these record types:

- `SYSCALL`
- `EXECVE`
- `CWD`
- `PATH`

## Fidelity Strategy

1. Use real key layout and nesting from `example_logs/audit.log` and
   `example_logs/ebpf.jsonl`.
2. Keep key presence strict and deterministic.
3. Normalize volatile runtime-only values before structural comparison.

## Normalized Volatile Fields

The following fields are normalized in fidelity tests because their exact values
are not contract-stable across runs:

- timestamps (`ts`, `msg=audit(...)` time fragments)
- process IDs (`pid`, `ppid`)
- sequence counters (`audit` sequence IDs)
- container/namespace identifiers (`cgroup_id`)
- result-dependent ephemeral ports (`src_port`, `dst_port` in some real rows)

## Intentionally Omitted High-Variance Fields

These are omitted from strict value parity assertions and checked only for shape
or type:

- dynamic DNS answer ordering
- host/container IP assignments
- socket paths that include runtime IDs
- inode-like and capability fields from full audit PATH records

Rationale: those values vary by environment and run timing, but shape and
presence are stable and required for parser correctness.
