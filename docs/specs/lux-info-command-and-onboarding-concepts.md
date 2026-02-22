# Spec: `lux info` Command For Concepts And First-Run Onboarding

Status: implemented
Owner: codex
Created: 2026-02-22
Last updated: 2026-02-22

## Problem
Users can run `lux`, but many do not understand key lifecycle terms used by the
CLI (`runtime`, `collector-only`, `provider plane`). This causes onboarding
friction and uncertainty about what to run first.

We also need one concise, reliable place that explains the "just get it
working" sequence in 3-5 steps.

## Goals
- Add a dedicated `lux info` command that explains core Lux concepts in plain
  language.
- Include concise first-run quickstart guidance in `lux info` with explicit
  provider-agnostic tracks for:
  - manual provider plane + `lux tui` startup
  - shim-enabled startup
- Keep existing technical `--help` command descriptions unchanged in this
  change.
- Keep output deterministic and scriptable when `--json` is used.
- Align CLI contracts/docs with the new onboarding surface.

## Non-Goals
- Rewriting existing `--help` about strings into plain language.
- Changing lifecycle behavior, startup semantics, or setup wizard flow.
- Adding a broader tutorial subsystem or remote documentation fetch.
- Changing evidence schemas, attribution rules, or trust boundaries.

## User Experience
New command:

```bash
lux info
```

`lux info` provides:
- A short high-level statement of what Lux does.
- A plain-language glossary for key technical terms already present in CLI
  help.
- Two concise "just get it working" sequences:
  - manual provider plane + `lux tui` path
  - shim-enabled path
- Pointers to next commands and contract docs for deeper detail.

`lux --help` and subcommand help remain technical and terse, with the only
functional addition being discoverability of the new `info` subcommand.

## Design
### 1) CLI surface
- Add top-level command:
  - `lux info`
- Add short `about` for discoverability in subcommand list.

No behavior changes to existing commands.

### 2) `lux info` text output structure
Human-readable `lux info` output is sectioned and stable:
1. What Lux is
2. Core concepts (term -> plain-language meaning)
3. Quickstart track A: manual provider plane + `lux tui`
4. Quickstart track B: shim-enabled startup
5. Next commands for common workflows
6. Docs pointers

Initial concept mappings include:
- runtime control plane
- collector plane / `--collector-only`
- provider plane
- UI service
- shims

### 3) Quickstart content contract
`lux info` includes two first-run quickstart tracks, both provider-agnostic
first (use `<provider>` placeholder, with optional examples such as `codex`):

Track A (manual lifecycle and TUI):
1. `lux setup`
2. `lux up --collector-only --wait`
3. `lux ui up --wait`
4. `lux up --provider <provider> --wait`
5. `lux tui --provider <provider>`

Track B (shims enabled):
1. `lux setup`
2. `lux shim enable` (or `lux shim enable <provider>`)
3. `lux up --collector-only --wait`
4. `lux ui up --wait`
5. `<provider>` (run provider CLI by name via shim)

Track notes:
- Track A explicitly demonstrates manual provider plane startup plus manual TUI
  startup (`lux up --provider ...` then `lux tui --provider ...`).
- Track B explicitly demonstrates shim-enabled startup where running
  `<provider>` enters provider TUI and ensures provider plane startup.
- For both tracks, examples should note that TUI/shim execution must run inside
  the active workspace (or use `--start-dir` where supported).
- Provider examples remain provider-agnostic first; `codex` may be shown only
  as an optional example.

Both tracks include a short follow-up note to inspect evidence (for example
`lux logs stats --latest` or `lux logs tail --latest`).

All quickstart tracks are concise and command-first, with no long prose between
steps.

### 4) JSON mode
When called with global `--json`, `lux info` returns structured data:
- `ok: true`
- `result` with keys:
  - `overview` (string)
  - `concepts` (array of `{term, meaning}`)
  - `quickstart` (array of tracks: `{id, title, provider_agnostic, steps[]}`)
    - each `steps[]` entry: `{step, command, note}`
  - `next` (array of `{goal, command}`)
  - `docs` (array of `{path, purpose}`)

This keeps onboarding content testable and machine-consumable.

### 5) Help-language preservation
Scope guard for this spec:
- Existing top-level/subcommand help descriptions stay as-is.
- Only additive help changes are allowed:
  - listing the new `info` subcommand
  - optional short pointer lines to `lux info` where already appropriate

## Data / Schema Changes
No collector/harness/UI evidence schema changes.

CLI contract change:
- New top-level command `info`
- New JSON `result` shape for `lux info --json` only

No changes to `JSON Error Envelope`.

## Security / Trust Model
No trust boundary changes.

`lux info` is read-only guidance output and does not start/stop services,
modify config, or mutate host files.

## Failure Modes
- Render/format failure when generating `lux info` output:
  - command exits non-zero with standard CLI error envelope in JSON mode.
- Unknown output regression (missing quickstart or concept entries):
  - caught by CLI tests and contract-doc tests.

## Acceptance Criteria
- `lux info` exists and exits zero in normal conditions.
- `lux info` includes:
  - overview
  - core concept explanations for runtime/collector-only/provider plane
  - provider-agnostic quickstart guidance with both:
    - manual provider plane + `lux tui` track
    - shim-enabled track
- `lux info --json` returns deterministic structured output with `overview`,
  `concepts`, `quickstart`, `next`, and `docs`.
- Existing technical help descriptions for current commands remain unchanged.
- `lux --help` lists the new `info` subcommand.
- `docs/contracts/cli.md` documents `info` behavior and intended purpose.
- `README.md` and install/contract docs link to `lux info` as onboarding entry.
- All repository tests pass, including:
  - `uv run python scripts/all_tests.py --lane fast`
  - `uv run python scripts/all_tests.py --lane pr`
  - `uv run python scripts/all_tests.py --lane full`

## Test Plan
- Unit tests:
  - formatter/build function for `lux info` sections (text + JSON payload).
  - ordering and presence checks for quickstart steps.
- Fixture cases:
  - none (no data-pipeline contract changes).
- Integration coverage:
  - CLI tests in `lux/tests/cli.rs` for:
    - `lux info` text sections
    - `lux info --json` shape
    - `lux --help` contains `info`
    - existing help strings for unchanged commands remain exact
- Regression tests:
  - guard against accidental replacement of technical help text with rewritten
    plain-language descriptions in this scope.
- Manual verification:
  - run `lux info` and confirm it is readable end-to-end in terminal output.
  - run `lux --help` and verify command descriptions are unchanged except new
    `info` listing.

## Rollout
- Land spec first, then implementation + tests + docs in one change set.
- No backwards compatibility requirement in stealth phase, but docs/tests must
  update atomically with behavior.

## Open Questions
- None.
