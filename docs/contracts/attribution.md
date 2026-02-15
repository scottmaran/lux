# Ownership and Attribution (Sessions, Jobs, PID Lineage)
Layer: Contract

This document defines how collector events are attributed to a harness session
or job, and what "agent-owned" means in filtered outputs.

It applies to:
- `collector-audit-filter` (`collector/scripts/filter_audit_logs.py`)
- `collector-ebpf-filter` (`collector/scripts/filter_ebpf_logs.py`)
- The merged timeline (`collector-merge-filtered`)

## Vocabulary
- **Run**: one `lasso up` lifecycle. Logs are run-scoped under
  `logs/<run_id>/...`.
- **Session**: one interactive TUI session. Metadata lives under
  `logs/<run_id>/harness/sessions/<session_id>/meta.json`.
- **Job**: one non-interactive `/run` invocation. Metadata lives under
  `logs/<run_id>/harness/jobs/<job_id>/input.json` and `status.json`.
- **Agent-owned**: an OS event that is attributable to the agent process tree
  for a given session/job (as opposed to background VM/container noise).

## Run markers written by the harness
The harness persists "root markers" that anchor attribution:
- `root_pid`: the run root process ID (namespaced PID as observed inside the VM)
- `root_sid`: the Linux session id (SID) for that run root process

Why both exist:
- PID lineage is the primary attribution mechanism.
- `root_sid` exists as a fallback for concurrent startup races where PID lineage
  is not yet known when early events arrive.

Where they are stored:
- TUI sessions: `meta.json` includes `root_pid` and `root_sid`.
- Jobs: both `input.json` and `status.json` include `root_pid` and `root_sid`.

## Attribution inputs available to the collector
The collector has two key event sources:
- auditd (raw `audit.log`): provides strong PID/PPID and exec lineage (`key="exec"`).
- eBPF (raw `ebpf.jsonl`): provides network + IPC metadata with PID attribution.

The collector uses audit exec events as the source of truth for PID lineage.
Even for eBPF events, ownership is computed by following the PID tree derived
from audit execs.

## Ownership assignment precedence (current behavior)
When assigning an event to an owner (session/job), the filters apply this order:

1. **Root PID / PID lineage**:
   - If an event pid is the `root_pid` for a known session/job, attribute to it.
   - Otherwise, walk `pid -> ppid -> ...` until an ancestor matches a known root.

2. **Cached PID-to-run mapping**:
   - Once a pid is attributed, future events from that pid can reuse the cached
     mapping (bounded by any configured PID TTL).

3. **Root SID fallback**:
   - If PID lineage does not resolve, look up the process SID and match it
     against known `root_sid` values from harness metadata.

4. **Unknown owner**:
   - If none apply, the event is considered unattributed.

Important nuance:
- In collector-only runs (no harness metadata), there may be no roots to match.
  In that case, filters can still emit agent-owned rows based on UID/root-comm
  heuristics, but `session_id` will remain `"unknown"`.

## Startup races and buffering
Two buffering behaviors exist to avoid polluting the merged timeline with
ownerless rows during startup windows:
- Audit filter: in `--follow` mode, it buffers early owned audit events briefly
  and drops events that remain unattributed after the delay.
- eBPF filter: in `--follow` mode, it can use a bounded pending buffer to hold
  early events until ownership becomes known (TTL + size bounds).

The summary stage (`collector-ebpf-summary`) also drops unattributed rows
(`session_id="unknown"` with no `job_id`) rather than emitting ownerless
timeline rows.

## Debugging misattribution
When attribution looks wrong:
1. Confirm harness markers exist for the run:
   - `logs/<run_id>/harness/sessions/*/meta.json` includes `root_pid` + `root_sid`
   - `logs/<run_id>/harness/jobs/*/input.json` and `status.json` include markers
2. Inspect raw exec lineage:
   - `logs/<run_id>/collector/raw/audit.log` for `key="exec"` events
3. Inspect filtered stage outputs:
   - `filtered_audit.jsonl` and `filtered_ebpf.jsonl` for `"session_id":"unknown"`
4. If issues are concurrency-related, verify `root_sid` fallback is active and
   that SIDs are being resolved correctly for the relevant PIDs.

