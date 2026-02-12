#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge filtered audit/eBPF logs into a unified timeline.")
    parser.add_argument(
        "--config",
        default=os.getenv("COLLECTOR_MERGE_CONFIG", "/etc/collector/merge_filtering.yaml"),
        help="Path to merge_filtering.yaml",
    )
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if yaml:
        return yaml.safe_load(content) or {}
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise SystemExit("collector-merge-filtered: missing PyYAML and config is not valid JSON") from exc


def parse_ts(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    value = ts.rstrip("Z")
    if "." in value:
        base, frac = value.split(".", 1)
        frac = (frac + "000000")[:6]
        value = base + "." + frac
    try:
        return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def normalize_event(event: dict, source_default: str, schema_version: str) -> dict:
    source = event.get("source") or source_default
    common_keys = {
        "schema_version",
        "session_id",
        "job_id",
        "ts",
        "source",
        "event_type",
        "pid",
        "ppid",
        "uid",
        "gid",
        "comm",
        "exe",
        "agent_owned",
    }
    details = {}
    for key, value in event.items():
        if key in common_keys:
            continue
        details[key] = value

    normalized = {
        "schema_version": schema_version,
        "session_id": event.get("session_id", "unknown"),
        "ts": event.get("ts"),
        "source": source,
        "event_type": event.get("event_type"),
    }
    for key in ("job_id", "pid", "ppid", "uid", "gid", "comm", "exe"):
        if key in event:
            normalized[key] = event.get(key)
    if details:
        normalized["details"] = details
    else:
        normalized["details"] = {}
    return normalized


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    schema_version = cfg.get("schema_version", "timeline.filtered.v1")

    inputs = cfg.get("inputs", [])
    audit_input_override = os.getenv("COLLECTOR_FILTER_OUTPUT")
    ebpf_input_override = os.getenv("COLLECTOR_EBPF_SUMMARY_OUTPUT")
    output_path = os.getenv("COLLECTOR_MERGE_FILTER_OUTPUT") or cfg.get("output", {}).get(
        "jsonl", "/logs/filtered_timeline.jsonl"
    )
    sort_strategy = cfg.get("sorting", {}).get("strategy", "ts_source_pid")

    rows = []
    for source_cfg in inputs:
        path = source_cfg.get("path")
        source_default = source_cfg.get("source") or ""
        if source_default == "audit" and audit_input_override:
            path = audit_input_override
        elif source_default == "ebpf" and ebpf_input_override:
            path = ebpf_input_override
        if not path or not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                normalized = normalize_event(event, source_default, schema_version)
                ts_dt = parse_ts(normalized.get("ts"))
                rows.append((ts_dt, normalized))

    if sort_strategy == "ts_source_pid":
        rows.sort(
            key=lambda item: (
                item[0] or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
                item[1].get("source") or "",
                item[1].get("pid") or 0,
            )
        )
    else:
        rows.sort(key=lambda item: item[0] or dt.datetime.min.replace(tzinfo=dt.timezone.utc))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as writer:
        for _, row in rows:
            writer.write(json.dumps(row, separators=(",", ":")) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
