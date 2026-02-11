# Lasso Test Principles

This file is a concise supplement to `tests/README.md`.
If there is a conflict, `tests/README.md` is authoritative.

## Core Principles
1. Behavior-first:
   - tests describe externally observable behavior and invariants.
2. Determinism:
   - expectations are explicit; failures are binary and reproducible.
3. Isolation:
   - test resources are per-test/per-trial; teardown is unconditional.
4. Layer boundaries:
   - unit/fixture for deterministic contract checks,
   - integration/stress/regression for live-stack acceptance.
5. Diagnosability:
   - failures must include enough artifact/log context to debug quickly.
6. No silent weakening:
   - if behavior changes, update tests intentionally; do not loosen assertions
     to hide regressions.

## Practical Implications
- Do not use offline synthetic replay as integration acceptance evidence.
- Keep fixture schema and timeline invariants enforced in code.
- Keep integration compose wiring anchored to shipping `compose.yml`, with only
  minimal test-only override deltas.
- Enforce compose parity/contracts in tests (see
  `tests/unit/test_compose_contract_parity.py`) to block drift.
- For Codex lanes, validate real behavior:
  - `agent_codex` `exec` path,
  - interactive TUI path with input/output/ownership evidence.

## Canonical Execution Surface
Use `uv` commands and `scripts/all_tests.py` lanes as the standard interface
for local and CI-representative runs.
