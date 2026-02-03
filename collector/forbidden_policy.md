# Forbidden Policy Schema (v1)

This document defines the detection-first policy format for forbidden command detection.
Policies are evaluated against the filtered audit/eBPF logs and emit alert rows into the
unified timeline.

## Top-level
- `schema_version`: fixed `forbidden.policy.v1`
- `policy` (object): policy metadata + defaults + rules

## policy
- `name` (string)
- `description` (string)
- `defaults` (object): default values applied to rules
  - `action` (string): e.g. `alert`
  - `severity` (string): e.g. `low`, `medium`, `high`
  - `enabled` (bool)
- `rules` (array)

## rule
- `id` (string, required)
- `description` (string)
- `enabled` (bool, optional)
- `severity` (string, optional)
- `action` (string, optional)
- `event_type` (string, optional)
- `event_type_any` (array, optional)
- `source` (string, optional)
- `source_any` (array, optional)
- `match` (object, optional)

## match fields
All match fields are ANDed together. Most fields accept either:
- a scalar (string/int)
- a list
- an object with `any: [...]`

Supported fields:
- `comm`: exact match against process name
- `exe`: exact match against executable path
- `cmd_contains`: substring match against command string
- `cmd_regex`: regex match against command string
- `path_prefix`: prefix match against filesystem path
- `path_regex`: regex match against filesystem path
- `dst_port`: exact match against destination port
- `dst_ip`: exact match against destination IP
- `protocol`: exact match against network protocol
- `dns_suffix`: suffix match against DNS names (case-insensitive)
- `dns_regex`: regex match against DNS names

## Alert output
Each matching rule emits an `alert` event in `filtered_alerts.jsonl`, which is merged into
`filtered_timeline.jsonl` with `source=policy` and `event_type=alert`. The alert details
include rule metadata, severity/action, and a human-readable subject.
