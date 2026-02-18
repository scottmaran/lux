# Lux: Agent Operating Contract
Layer: Contract

This repo is designed for AI-driven autonomous development. If you are an AI agent
working in this repo, treat this document as normative.

## Core Principles
- Ease of use for the user.
- Sustainable agentic design: work is attributable, reviewable, and reproducible.
- Comprehensive automated coverage: tests define observable behavior.

## Product Vision (North Star)
- The go-to source for agent observability.
- Users can run third-party agents and get auditable, structured evidence of what happened.
- Observation must not depend on agent cooperation (provider-agnostic).

## Non-Negotiable Product Invariants
- We log everything an agent does within Lux's observable scope.
- The user can be confident that the agent can't tamper with the logs.
- Each log must be attributable to a specific agent/session.
- We are independent of the agent program itself (Codex/Claude/etc).

See `INVARIANTS.md`. If you change behavior that could affect an invariant,
keep the invariant true and update tests/documentation so enforcement remains explicit.
Do not change invariants (or weaken them) without explicit user approval.
Clarifications are allowed; meaning changes require approval and a written record
in the relevant spec/docs/tests.

## Backwards Compatibility
- We are in stealth. Backwards compatibility is not a constraint today.
- Behavior changes still require updating tests and documentation.

## Where Truth Lives (Priority Order)
Normative (must be kept correct):
- `AGENTS.md`: how to do work here.
- `docs/agents/classes/*`: agent task classes and their required workflows.
- `docs/specs/*`: implementable change contracts for non-trivial work.
- `INVARIANTS.md`: product invariants and trust model.
- `tests/README.md`: the test suite is the specification for observable behavior.
- `docs/contracts/*`: user-facing behavior of the `lux` CLI and runtime.
- Component docs: `agent/README.md`, `harness/README.md`, `collector/README.md`,
  `ui/README.md`, `lux/README.md`.
- Schema contracts under `docs/contracts/schemas/*` (raw/filtered/timeline formats).

Reference / background (useful, but not a contract):
- `docs/history/*`: narrative and implementation log.
- `docs/dev/example_flow.md`: illustrative walkthrough; may lag reality.
- `docs/research/*`: curated external notes. Use them to inform decisions,
  then translate conclusions into repo-native contracts (specs/tests).

## Abstraction Level (Doc Layers)
Lux is an agent observability system. Current implementation details (Docker/VM,
specific sensors, file paths, component wiring) are not the product and may change.

When writing or editing docs/specs, explicitly choose the layer:
- Invariant: timeless product principles; must survive major architecture changes.
- Contract: externally visible behavior (schemas/APIs/CLI); versioned but durable.
- Implementation: how the current system achieves the contract today.

Rule: `INVARIANTS.md` must be written at the Invariant layer (no hard dependency
on Docker/VM/specific sensors/paths). Put "how we currently do it" in
Implementation-layer docs instead.

## Choose An Agent Class
Every task must pick exactly one class and follow its contract:
- Brainstorm: `docs/agents/classes/brainstorm.md`
- Create Spec: `docs/agents/classes/create_spec.md`
- Implement Spec: `docs/agents/classes/implement_spec.md`
- Audit: `docs/agents/classes/audit.md`
- Explain: `docs/agents/classes/explain.md`
- One Off: `docs/agents/classes/one_off.md`

Agents must state the chosen class at the top of each response; if reclassifying mid-stream, announce it.
If a task changes class mid-stream, call out the transition explicitly and
ensure any in-flight spec/docs reflect the new goal/scope.

## Default Workflow (For Changes In This Repo)
1. Read `AGENTS.md`, then the chosen class doc under `docs/agents/classes/`.
2. Identify the contract you are changing (tests, schema docs, user docs).
3. If the change is non-trivial, write/update a spec under `docs/specs/`.
4. Implement in small slices.
5. Add or update tests so the new behavior is enforced.
6. Run the smallest gate that proves correctness, then widen as needed (see Verification Gates below).
7. Update documentation affected by the change.

## Verification Gates
Canonical local commands:
- `uv sync`
- `uv run python scripts/all_tests.py --lane fast`
- `uv run python scripts/all_tests.py --lane pr`
- `uv run python scripts/all_tests.py --lane full`

## Repo Map (Quick Orientation)
- `lux/`: Rust CLI source.
- `collector/`: auditd/eBPF capture plus filter/summarize/merge pipeline.
- `harness/`: session/job runner (PTY/TUI + API) and artifact writer.
- `agent/`: agent container and provider auth bootstrapping.
- `ui/`: UI and API server for log review.
- `docs/`: user guide, developer docs, specs/audits.
- `tests/`: specification for observable behavior.
- `scripts/`: canonical test runners and verification helpers.

## Guardrails
- No silent behavior changes: update tests and schema/docs together.
- Prefer deterministic evidence over natural-language assertions.
- Never commit secrets or credentials.
- Avoid destructive actions unless explicitly requested (data deletion, resets, force pushes).
