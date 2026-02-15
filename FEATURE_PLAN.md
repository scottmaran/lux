# Feature Plan: Docs Refactor (Invariant / Contract / Implementation Layers)

Status: draft
Owner: scottmaran + agents

## Goals
- Make `AGENTS.md` and `INVARIANTS.md` the durable entrypoints for autonomous work.
- Centralize all durable external-facing behavior under `docs/contracts/`.
- Separate "what must be true" (invariants/contracts) from "how it works today" (implementation/architecture).
- Make `docs/README.md` the single, unambiguous navigation map.
- Reduce "where is the truth?" ambiguity for agents and humans.
- Establish a single repo glossary to keep vocabulary consistent across invariants, specs, and contracts.

## Non-Goals
- Backwards compatibility for old doc paths (repo is in stealth).
- Changing runtime behavior (this is documentation-only).
- Perfect doc-link automation on day 1 (we will use simple `rg`-driven updates first).

## Design Principles
- Every foundational doc should sit at an explicit layer:
  - Invariant: timeless product principles (example: `INVARIANTS.md`).
  - Contract: externally visible behavior (CLI/API/schemas/artifacts/log layout).
  - Implementation: current architecture/topology/mechanisms/constraints.
- Contracts are centralized (canonical source lives under `docs/contracts/`).
- Component READMEs remain near code and link to the canonical contracts.
- Prefer stable filenames and shallow trees; do large reorganizations rarely and intentionally.
- Add a tiny per-file layer header (for example `Layer: Contract`) so a single file remains self-describing when viewed out of context.
  - Rule: one plain-text line immediately after the H1: `Layer: Invariant|Contract|Implementation` (no additional metadata lines).

## Target Documentation Tree
```text
docs/
  README.md
  glossary.md                       # shared vocabulary

  agents/
    README.md
    classes/
      brainstorm.md
      create_spec.md
      implement_spec.md
      audit.md
      explain.md
      one_off.md

  contracts/
    README.md
    install.md
    cli.md
    config.md
    platform.md
    log_layout.md
    harness_api.md
    harness_artifacts.md
    ui_api.md
    attribution.md
    collector_config/                # collector pipeline knobs (durable semantics)
      README.md
      auditd.md
      auditd_rules.md
      audit_filtering.md
      ebpf_filtering.md
      ebpf_summary.md
      merge_filtering.md
    schemas/
      README.md
      auditd.raw.md
      auditd.filtered.v1.md
      ebpf.raw.md
      ebpf.filtered.v1.md
      ebpf.summary.v1.md
      timeline.filtered.v1.md

  architecture/
    README.md
    overview.md                      # short "how it works today"
    design_doc.md                    # current long-form design prompt/doc (non-normative)
    platform_notes.md
    deployments/
      docker_desktop_vm.md
      lasso_vm_layout.md
    sensors/
      kernel_auditing_info.md
    ui_design.md

  dev/
    README.md
    developing.md
    example_flow.md

  specs/
    README.md
    TEMPLATE.md

  audits/
    README.md
    TEMPLATE.md

  history/
    ...

  research/
    README.md
    ...
```

## Migration Map (Current -> Target)

### Agents
- `docs/agent_classes/` -> `docs/agents/classes/`

### Contracts (from `docs/guide/`)
- `docs/guide/install.md` -> `docs/contracts/install.md`
- `docs/guide/cli.md` -> `docs/contracts/cli.md`
- `docs/guide/config.md` -> `docs/contracts/config.md`
- `docs/guide/log_layout.md` -> `docs/contracts/log_layout.md`

### Contracts (from component docs)
- `harness/api.md` -> `docs/contracts/harness_api.md`
- `harness/artifacts.md` -> `docs/contracts/harness_artifacts.md`
- `docs/ui/UI_API.md` -> `docs/contracts/ui_api.md`

### Contracts (schemas + attribution)
- `collector/auditd_raw_data.md` -> `docs/contracts/schemas/auditd.raw.md`
- `collector/auditd_filtered_data.md` -> `docs/contracts/schemas/auditd.filtered.v1.md`
- `collector/ebpf_raw_data.md` -> `docs/contracts/schemas/ebpf.raw.md`
- `collector/ebpf_filtered_data.md` -> `docs/contracts/schemas/ebpf.filtered.v1.md`
- `collector/ebpf_summary_data.md` -> `docs/contracts/schemas/ebpf.summary.v1.md`
- `collector/timeline_filtered_data.md` -> `docs/contracts/schemas/timeline.filtered.v1.md`
- `collector/ownership_and_attribution.md` -> `docs/contracts/attribution.md`

### Contracts (collector config semantics)
Move the config *documentation* (not the YAML) into contracts so the semantics are centralized:
- `collector/config/auditd.md` -> `docs/contracts/collector_config/auditd.md`
- `collector/config/auditd_rules.md` -> `docs/contracts/collector_config/auditd_rules.md`
- `collector/config/audit_filtering.md` -> `docs/contracts/collector_config/audit_filtering.md`
- `collector/config/ebpf_filtering.md` -> `docs/contracts/collector_config/ebpf_filtering.md`
- `collector/config/ebpf_summary.md` -> `docs/contracts/collector_config/ebpf_summary.md`
- `collector/config/merge_filtering.md` -> `docs/contracts/collector_config/merge_filtering.md`
- `collector/config/README.md` -> `docs/contracts/collector_config/README.md`

Keep the actual shipped config files co-located with the collector:
- `collector/config/*.yaml`, `collector/config/*.conf`, `collector/config/rules.d/*` remain in place.

Drift prevention:
- Leave a short `collector/config/README.md` stub behind that points to the canonical `docs/contracts/collector_config/README.md`.

### Architecture (implementation-layer)
- `docs/vm/docker_desktop_vm.md` -> `docs/architecture/deployments/docker_desktop_vm.md`
- `docs/vm/lasso_vm_layout.md` -> `docs/architecture/deployments/lasso_vm_layout.md`
- `docs/orientation/kernel_auditing_info.md` -> `docs/architecture/sensors/kernel_auditing_info.md`
- `docs/ui/UI_DESIGN.md` -> `docs/architecture/ui_design.md`

### Dev docs (implementation-layer)
- `docs/dev/DEVELOPING.md` -> `docs/dev/developing.md`
- `docs/dev/EXAMPLE_FLOW.md` -> `docs/dev/example_flow.md`

### Research (non-normative)
- `docs/knowledge_base/` -> `docs/research/`

### Split: Platform
Current `docs/orientation/platform.md` should be split into:
- `docs/contracts/platform.md`: supported environments and externally visible guarantees.
- `docs/architecture/platform_notes.md`: current constraints, TODOs, and implementation notes.

### Split: Overview/Design Doc
Current `docs/orientation/overview.md` should become:
- `docs/architecture/design_doc.md`: preserve current long-form content as non-normative.
- `docs/architecture/overview.md`: create a short "how it works today" overview.

### Delete / Retire
- `docs/ARCHITECTURE.md` is currently empty; remove it unless repurposed.

## Implementation Steps (Phased)

### Phase 0: Preflight
- Create target directories (empty README stubs where appropriate).
- Decide and document contract versioning policy for `docs/contracts/schemas/` (keep existing schema version tags in filenames).
- Note for macOS (case-insensitive filesystems): case-only renames may require an intermediate filename.
  Example: `git mv docs/dev/DEVELOPING.md docs/dev/DEVELOPING.tmp.md && git mv docs/dev/DEVELOPING.tmp.md docs/dev/developing.md`.
- Decide the exact format for layer headers and apply it consistently:
  - One plain-text line immediately after the H1:
    - `Layer: Contract`
    - `Layer: Implementation`
    - `Layer: Invariant`

### Phase 1: Mechanical Moves
- Use `git mv` for all moves listed above to preserve history.
- Do not change content yet other than fixing obviously broken intra-doc links created by the move.

### Phase 2: Splits + Layer Cleanup
- Perform the platform split (contract vs implementation).
- Perform the overview split (design doc vs short overview).
- Ensure each moved doc matches its layer:
  - Contracts must describe externally visible behavior and durable semantics.
  - Architecture docs may contain topology/sensors/mechanisms and can change freely.

### Phase 3: Navigation Rebuild
- Rewrite `docs/README.md` into the canonical index, grouped by:
  - Audience: User, Agent, Developer
  - Layer: Invariant, Contract, Implementation
- Add `docs/contracts/README.md` and `docs/architecture/README.md` as local indexes.
- Add `docs/agents/README.md` as a small agent navigation hub (optional).
- Add `docs/glossary.md` and ensure `INVARIANTS.md` terms link back to it.

### Phase 4: Link/Reference Update Pass
- Update references across:
  - `README.md`
  - `AGENTS.md`
  - `docs/README.md`
  - component READMEs under `agent/`, `harness/`, `collector/`, `ui/`, `lasso/`
  - tests that reference docs (if any)
- Run `rg` searches to ensure old paths are gone:
  - `rg -n "docs/guide/|docs/orientation/|docs/vm/|docs/agent_classes/|docs/knowledge_base/" -S .`

## Open Questions / Follow-ups
- Do we want directory placement alone to imply layer for non-foundational docs, or should we require layer headers everywhere (even under `history/` and `research/`)?

## Verification
- Verify no references to old doc paths remain (`rg` as above).
- Ensure `docs/README.md` is accurate and points to real files.
- Optional: run `uv run python scripts/all_tests.py --lane fast` to ensure no tests rely on old doc paths.

## Acceptance Criteria
- There is exactly one documentation map: `docs/README.md`.
- Contracts are centralized under `docs/contracts/`.
- Architecture notes are under `docs/architecture/` and clearly marked non-normative.
- Agents can reliably answer: "Where is the contract for X?" in under 60 seconds.
- No lingering references to removed/moved directories.
