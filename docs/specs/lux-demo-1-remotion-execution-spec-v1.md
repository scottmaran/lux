# Spec: Lux Demo 1 Remotion Execution Spec V1

Status: draft
Owner: codex
Created: 2026-02-27
Last updated: 2026-02-27

## Problem
Lux needs a first demo video (`lux_demo`) that clearly communicates the product's core value: agent UI output is a claim, while Lux provides independent, attributable evidence of what happened locally.

The current storyboard direction is agreed in principle (real incident first, then simulated threat), but there is no implementation-grade Remotion contract that defines exact scene timing, visual composition, and data payloads.

Without this spec, implementation risk is high:
- Story drift (message ambiguity between "misleading" vs "malicious").
- Visual drift (layout not matching intended screenshot-like composition).
- Engineering drift (subagent invents payloads/timing during implementation).

## Goals
- Define a production-ready V1 execution plan for `lux_demo` in Remotion.
- Preserve narrative structure:
  - Real Codex incident first (grounded truth).
  - Simulated provider-agnostic threat second (dramatic escalation).
- Specify scene-by-scene frame goals at 60 FPS.
- Specify component mapping from existing `video-kit` primitives to each scene.
- Specify concrete payloads for terminal text, prompts, and Lux timeline entries.
- Keep messaging aligned with Lux invariants and trust model.

## Non-Goals
- Finalize audience-specific cut variants (security/dev/general) in V1.
- Finalize music/sound design beyond optional click/typing cues.
- Claim or imply real malicious behavior by any named provider in the simulated segment.
- Implement code in this spec task.

## User Experience
The viewer sees a black cold open, then a desktop-style composition with Lux UI on the left and terminal on the right (terminal in foreground with overlap).

The narrative then proceeds in two acts:
1. Real incident (Codex web-search rendering mismatch): Codex appears to have "searched ESPN", but Lux timeline shows no local ESPN egress.
2. Simulated threat (provider-agnostic): agent claims no external uploads; Lux timeline shows suspicious file reads + outbound upload.

The close reinforces the value proposition:
- Agent output is a claim.
- Lux provides independently collected, attributable evidence.

No voiceover is used; messaging is delivered through terminal text, Lux timeline text, and explicit on-screen callouts.

## Design
### Runtime + composition defaults
- Resolution: `1920x1080`
- FPS: `60`
- Composition ID (planned): `LuxDemo01`
- Planned total duration: `2400` frames (`40s`)
- Project location (planned): `marketing/remotion/projects/lux_demo`

### Scene-by-scene frame goals
| Scene | Frames (inclusive) | Duration | Goal |
|---|---:|---:|---|
| S0 Cold Open | 0-89 | 1.5s | Establish thesis: "Agent output is not evidence." |
| S1 Setup + Layout Establish | 90-389 | 5.0s | Show `lux setup --defaults`; bring in Lux UI left + terminal right with overlap. |
| S2 Codex Session Start | 390-629 | 4.0s | Start `codex` session and issue ESPN prompt. |
| S3 Real Incident Evidence | 630-1109 | 8.0s | Show Codex "Searched ESPN" lines while Lux timeline shows only provider-related traffic. |
| S4 Bridge Clarification | 1110-1259 | 2.5s | Clarify this may be non-malicious but still misleading for local attribution. |
| S5 Simulated Threat Setup | 1260-1619 | 6.0s | Start provider-agnostic agent and show reassuring claim text. |
| S6 Simulated Threat Evidence | 1620-2159 | 9.0s | Lux timeline reveals sensitive file reads + outbound POST; high-contrast callouts. |
| S7 Closing Value Statement | 2160-2399 | 4.0s | Close on Lux promise + brand CTA line. |

### Layout contract (desktop composition)
Target visual: similar to provided screenshot.

- Base background: near-black desktop field with subtle gradient.
- Lux UI window:
  - Positioned left-dominant.
  - Approx bounds: `x=36, y=120, w=1320, h=760`.
  - Appears behind terminal window.
- Terminal window:
  - Positioned right side with foreground overlap.
  - Approx bounds: `x=1080, y=215, w=780, h=430`.
  - `zIndex` above UI.
- Overlap requirement:
  - Visible overlap between terminal and UI of at least `180px` in x-axis.

### Motion contract
- Window entrances use spring-based easing (`spring(...)`) rather than linear moves.
- Terminal arrives first, Lux UI follows shortly after setup command starts.
- Callouts fade/slide in with clamped interpolation (`interpolate(..., {extrapolateLeft/Right: 'clamp'})`).
- Threat segment (S6) should increase urgency via color contrast + pacing, not jump cuts.

### Component mapping
Use existing primitives where possible.

- From `packages/video-kit/src/terminal`:
  - `TerminalWindow`
  - `TypingText`
  - `ScrollingTerminal`
  - `MouseCursor` (optional in V1; preferred for clicks/run switches)
- From `packages/video-kit/src/lux-ui`:
  - `DashboardLayout`
  - `DashboardMetrics`, `DashboardRun`, `DashboardTimelineEvent` types
- Project-local components (planned):
  - `CalloutBanner` (short textual overlays for thesis/evidence statements)
  - `BrowserChrome` (optional wrapper for UI to display `localhost:8090` bar)
- Remotion primitives:
  - `AbsoluteFill`, `Sequence`, `interpolate`, `spring`, `useCurrentFrame`, `useVideoConfig`

### Copy contract (on-screen text)
#### S0
- `Agent output is not evidence.`
- `Lux demo #1` (smaller sublabel)

#### S1
- Terminal command: `lux setup --defaults`
- Supporting callout: `No instrumentation inside the agent required.`

#### S3 (real incident callouts)
- `Real incident (Feb 26, 2026)`
- `Codex TUI: "Searched https://www.espn.com/..."`
- `Lux timeline: no local egress to espn.com`
- `Inference: search happened provider-side, not on this machine`

#### S4
- `Not necessarily malicious.`
- `But UI text can mislead about what happened locally.`

#### S6 (simulated threat callouts)
- `Simulated threat scenario`
- `Agent claim: "No external uploads"`
- `Lux evidence: sensitive file reads + outbound POST`

#### S7
- `Agent output is a claim.`
- `Lux is independently collected evidence.`
- `Attributable logs for every run.`

### Data payloads
Payloads below are implementation defaults for V1. Minor copy edits are allowed if meaning is preserved.

#### 1) Setup terminal payload (`SETUP_LINES`)
```ts
[
  {text: '[lux] Writing config...', delay: 0},
  {text: '[lux] Starting collector + UI...', delay: 22},
  {text: '[lux] UI ready at http://localhost:8090', delay: 46},
  {text: '[lux] Tip: run your agent as usual (codex, claude, etc.)', delay: 72},
]
```

#### 2) Real incident terminal payload (`REAL_CODEX_LINES`)
Command:
```ts
'codex'
```
User prompt:
```ts
'Find the latest ESPN report on the Lakers injury list and summarize in 3 bullets with links.'
```
Agent output lines:
```ts
[
  {text: '[agent] Searched https://www.espn.com/...', delay: 0},
  {text: '[agent] Searched https://www.espn.com/.../story/_/id/...', delay: 24},
  {text: '[agent] Summary ready with ESPN links.', delay: 52},
]
```

#### 3) Real incident Lux UI payload (`REAL_INCIDENT_STATE`)
Runs:
```ts
[
  {id: 'session_codex_real', name: 'session_2026_codex', kind: 'session', mode: 'tui', started: 'Feb 26 at 01:39 AM'},
  {id: 'job_lux_setup', name: 'lux_setup_defaults', kind: 'job', status: 'completed', exitCode: 0, started: 'Feb 26 at 01:38 AM', ended: 'Feb 26 at 01:39 AM'},
]
```
Metrics:
```ts
{processes: 217, fileChanges: 0, networkCalls: 11}
```
Timeline events:
```ts
[
  {
    timestamp: 'Feb 26, 01:41:12 AM',
    source: 'ebpf',
    eventType: 'dns_query',
    target: 'resolve chatgpt.com',
    process: 'request-internal',
    pid: 77677,
  },
  {
    timestamp: 'Feb 26, 01:41:14 AM',
    source: 'ebpf',
    eventType: 'net_summary',
    target: 'POST chatgpt.com/backend-api/codex',
    process: 'request-internal',
    pid: 77677,
  },
  {
    timestamp: 'Feb 26, 01:41:18 AM',
    source: 'ebpf',
    eventType: 'net_summary',
    target: 'TLS ab.chatgpt.com:443',
    process: 'tokio-runtime-w',
    pid: 77677,
  },
  {
    timestamp: 'Feb 26, 01:41:35 AM',
    source: 'ebpf',
    eventType: 'dns_query',
    target: 'resolve raw.githubusercontent.com',
    process: 'request-internal',
    pid: 77677,
  },
  {
    timestamp: 'Feb 26, 01:41:40 AM',
    source: 'ebpf',
    eventType: 'net_summary',
    target: 'GET raw.githubusercontent.com/openai/...',
    process: 'request-internal',
    pid: 77677,
  },
]
```
Constraint: no `espn.com` entry appears in local timeline events.

#### 4) Simulated threat terminal payload (`THREAT_AGENT_LINES`)
Command:
```ts
'thirdparty-agent'
```
User prompt:
```ts
'Optimize this repo. Install what you need, but keep all data local.'
```
Agent output lines:
```ts
[
  {text: '[agent] Installing dependencies and optimizing...', delay: 0},
  {text: '[agent] Completed. No sensitive files accessed.', delay: 30},
  {text: '[agent] No external uploads performed.', delay: 56},
]
```

#### 5) Simulated threat Lux UI payload (`THREAT_STATE`)
Runs:
```ts
[
  {id: 'session_provider_unknown', name: 'session_provider_unknown', kind: 'session', mode: 'tui', started: 'Feb 26 at 01:44 AM'},
  {id: 'job_optimize_worker', name: 'optimize_worker', kind: 'job', status: 'running', started: 'Feb 26 at 01:44 AM'},
]
```
Metrics:
```ts
{processes: 43, fileChanges: 2, networkCalls: 29}
```
Timeline events:
```ts
[
  {
    timestamp: 'Feb 26, 01:44:16 AM',
    source: 'ebpf',
    eventType: 'file_read',
    target: 'read ~/.ssh/id_ed25519',
    process: 'python',
    pid: 88124,
    danger: true,
  },
  {
    timestamp: 'Feb 26, 01:44:19 AM',
    source: 'ebpf',
    eventType: 'file_read',
    target: 'read .env.production',
    process: 'python',
    pid: 88124,
    danger: true,
  },
  {
    timestamp: 'Feb 26, 01:44:25 AM',
    source: 'ebpf',
    eventType: 'dns_query',
    target: 'resolve sync-agent-cache.net',
    process: 'python',
    pid: 88124,
    danger: true,
  },
  {
    timestamp: 'Feb 26, 01:44:27 AM',
    source: 'ebpf',
    eventType: 'net_summary',
    target: 'POST sync-agent-cache.net:443/upload',
    process: 'python',
    pid: 88124,
    danger: true,
  },
  {
    timestamp: 'Feb 26, 01:44:28 AM',
    source: 'ebpf',
    eventType: 'net_summary',
    target: '200 OK (1.8 MB sent)',
    process: 'python',
    pid: 88124,
    danger: true,
  },
]
```
Constraint: this segment is explicitly labeled simulated.

## Data / Schema Changes
- Adds spec only in this task.
- Planned implementation adds a new Remotion marketing project under `marketing/remotion/projects/lux_demo`.
- No Lux runtime/collector/harness/UI product schema changes.
- No log-format contract changes.

## Security / Trust Model
This video messaging must remain consistent with `INVARIANTS.md`:
- Lux claims evidence inside an explicit observation boundary.
- Lux evidence is independent from agent self-reporting.
- The simulated segment must not be presented as a real attributed incident.

Trust-model guardrails in copy:
- Real segment: factual and date-anchored (`Feb 26, 2026`).
- Simulated segment: explicitly marked "Simulated threat scenario".
- Avoid claims that require attribution Lux cannot prove in-scene.

## Failure Modes
- Message confusion: viewer interprets real segment as malicious behavior.
  - Handling: include S4 bridge text (`Not necessarily malicious`).
- Message dilution: viewer misses why simulated segment follows real segment.
  - Handling: use bridge and explicit "simulated" label before escalation.
- Visual mismatch: windows do not match target left/right overlap composition.
  - Handling: enforce numeric layout contract and keyframe-based still checks.
- Overload: too much text per scene hurts readability.
  - Handling: max 2-3 callout lines visible at once; clamp line lengths.

## Acceptance Criteria
- Composition includes 8 scenes (S0-S7) with frame boundaries matching this spec within +/- 12 frames tolerance per scene.
- Terminal/UI layout matches target: Lux UI left, terminal right foreground, visible overlap.
- S3 contains all real-incident claims:
  - Codex explicitly named.
  - "Searched ESPN" appears in terminal agent lines.
  - Lux timeline contains no `espn.com` local egress entries.
- S6 is explicitly labeled simulated and provider-agnostic.
- No voiceover track is required; narrative clarity is achieved via text/callouts.
- Closing statement includes independent evidence + attribution message.

## Test Plan
- Unit tests:
  - Not required for this storyboard/spec-only change.
- Fixture cases:
  - Planned implementation should keep payload constants in a dedicated `src/config/payloads.ts` for deterministic review.
- Integration coverage:
  - `npm run lint` in `marketing/remotion/projects/lux_demo` passes.
  - `npm run build` in `marketing/remotion/projects/lux_demo` passes.
- Regression tests:
  - Planned implementation should include scripted still renders at scene checkpoints to prevent layout drift.
- Manual verification:
  - Render stills at frames: `45, 240, 510, 870, 1180, 1440, 1890, 2280`.
  - Confirm text readability and the real vs simulated labeling.

## Rollout
- Introduce as first Lux demo project (`lux_demo`) in marketing Remotion workspace.
- No backward compatibility commitments needed for marketing video internals.
- If this V1 performs well, create follow-up cuts by audience persona (security/dev/general) as separate compositions using same payload backbone.

## Open Questions
- Which closing CTA should be primary for V1:
  - `Run any agent. Keep an auditable trail of what actually happened.`
  - `If an agent lies, Lux gives you proof.`
- Whether to include optional subtle SFX (typing/click) in final export.
- Whether S1 should show `lux setup --defaults` only, or also briefly show `lux` first before setup.
