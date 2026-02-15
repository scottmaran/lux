# Schemas
Layer: Contract

This directory contains the canonical schema contracts for evidence artifacts
written to the sink.

Filenames include version tags where applicable (for example `*.v1.md`). When a
schema changes in a non-backwards-compatible way, add a new versioned contract
file rather than editing the old one in place.

## Index
- auditd raw: `docs/contracts/schemas/auditd.raw.md`
- auditd filtered: `docs/contracts/schemas/auditd.filtered.v1.md`
- eBPF raw: `docs/contracts/schemas/ebpf.raw.md`
- eBPF filtered: `docs/contracts/schemas/ebpf.filtered.v1.md`
- eBPF summary: `docs/contracts/schemas/ebpf.summary.v1.md`
- unified timeline: `docs/contracts/schemas/timeline.filtered.v1.md`
