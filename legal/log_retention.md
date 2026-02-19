# Log Retention and Deletion
Layer: Contract

This document defines Lux's open-source default retention behavior and the
operator policy expected for log cleanup.

## Current Product Behavior

- Lux writes run-scoped artifacts under `<log_root>/<run_id>/...`.
- `lux down` clears active-run state but does not delete historical run
  directories.
- Lux currently does not enforce automatic log deletion.

## Open-Source Operator Policy

Operators are responsible for defining and enforcing retention windows that fit
their legal and organizational requirements.

Minimum expected policy:

- keep logs only as long as needed for debugging/audit purposes,
- delete runs that are no longer needed,
- apply stricter retention for logs containing sensitive data.

## Recommended Baseline (Draft)

If you do not yet have an internal policy, start with:

- development/smoke runs: 14 days,
- incident or security review runs: 90 days,
- explicit legal hold cases: retained until hold is released.

## Safe Deletion Procedure

1. Confirm the target run is not active.
2. Identify the run directory under `<log_root>`.
3. Delete only the intended `<run_id>` directory (or selected artifacts within
   it), then verify removal.
4. Record deletion actions in your own operational log if required by policy.

## Data Sensitivity Reminder

Run artifacts may include prompt text, terminal output, and environment
metadata. Use `--capture-input=false` when appropriate and avoid placing secrets
in command arguments or environment variables unless required.

## Related Contracts

- `docs/contracts/log_layout.md`
- `docs/contracts/harness_artifacts.md`
- `docs/contracts/cli.md`
