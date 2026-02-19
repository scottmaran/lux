# Legal Use and Monitoring Consent
Layer: Contract

This document defines operator responsibilities when using Lux to observe agent
activity.

Lux is a recording/observability system. Depending on configuration and usage,
it can capture command activity and metadata that may be sensitive.

This is a product policy and usage contract, not legal advice.

## What Lux Records

In supported configurations, Lux can record:

- command execution and process metadata,
- filesystem activity metadata,
- network/IPC metadata,
- harness artifacts including prompt input, `stdin`/`stdout`/`stderr`, and job
  environment maps (see related contracts).

## Operator Responsibilities

Before using Lux in any environment with other users, operators must:

- ensure they have authority to monitor the environment,
- provide clear notice that recording is enabled,
- obtain any required consent under applicable laws/policies,
- avoid collecting unnecessary sensitive data,
- restrict access to logs to authorized reviewers only.

## Minimum Notice (Template)

The following notice is recommended before starting a recorded Lux run:

```text
This environment is monitored by Lux for agent observability and security review.
Agent actions and related metadata may be recorded (for example commands,
filesystem activity, network metadata, and run logs such as prompts/stdout/stderr).
Do not use this environment for personal or unrelated confidential activity.
```

## Prohibited Usage

Lux must not be used for:

- unlawful interception or surveillance,
- monitoring environments where the operator lacks authorization,
- bypassing policy obligations to notify monitored users.

## Related Contracts

- `docs/contracts/harness_artifacts.md`
- `docs/contracts/harness_api.md`
- `docs/contracts/schemas/timeline.filtered.v1.md`
- `docs/contracts/log_layout.md`
