# `auditd.conf` (Collector)
Layer: Contract

This repo ships an `auditd.conf` suitable for containerized auditing inside the
Docker Desktop Linux VM.

File:
- `collector/config/auditd.conf` (baked into the collector image as `/etc/audit/auditd.conf`)

## Key behavior
- `log_format = RAW`
  - We want raw, line-oriented audit records for deterministic parsing.
- `log_file = /logs/audit.log`
  - This is the base default, but **the collector entrypoint rewrites this**
    at runtime to match `COLLECTOR_AUDIT_LOG` (or `COLLECTOR_AUDIT_OUTPUT`).
  - See `collector/entrypoint.sh` for the exact `sed` behavior.
- `log_group = adm`
  - Matches Ubuntu defaults; the entrypoint tries to ensure files are owned
    `root:adm` and mode `0640`.

## Rotation / disk-pressure posture
- Rotation is enabled (`max_log_file_action = ROTATE`) with small log chunks
  to make local testing predictable.
- Disk-pressure actions are conservative (`disk_full_action = SUSPEND`,
  `disk_error_action = SUSPEND`) to avoid silently dropping audit events.

## Related docs
- Raw audit log format: `docs/contracts/schemas/auditd.raw.md`
- Audit rules (what gets logged): `docs/contracts/collector_config/auditd_rules.md`

