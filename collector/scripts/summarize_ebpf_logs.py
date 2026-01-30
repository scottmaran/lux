#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize filtered eBPF logs into network request rows.")
    parser.add_argument(
        "--config",
        default=os.getenv("COLLECTOR_EBPF_SUMMARY_CONFIG", "/etc/collector/ebpf_summary.yaml"),
        help="Path to ebpf_summary.yaml",
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
        raise SystemExit("collector-ebpf-summary: missing PyYAML and config is not valid JSON") from exc


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


def format_ts(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def protocol_candidate(value: str | None) -> str | None:
    if not value or value == "unknown":
        return None
    return value


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    schema_version = cfg.get("schema_version", "ebpf.summary.v1")
    input_path = Path(cfg.get("input", {}).get("jsonl", "/logs/filtered_ebpf.jsonl"))
    output_path = Path(cfg.get("output", {}).get("jsonl", "/logs/filtered_ebpf_summary.jsonl"))

    dns_by_pid_ip: dict[tuple[int, str], set[str]] = defaultdict(set)
    groups: dict[tuple[str, str | None, int, str, int], dict] = {}
    passthrough_rows: list[tuple[dt.datetime, dict]] = []

    if input_path.exists():
        with input_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("event_type")
                ts_raw = event.get("ts")
                ts_dt = parse_ts(ts_raw)
                if ts_dt is None:
                    continue

                if event_type == "dns_response":
                    pid = parse_int(event.get("pid"))
                    dns = event.get("dns") or event.get("details", {}).get("dns")
                    if pid is None or not isinstance(dns, dict):
                        continue
                    query_name = dns.get("query_name")
                    answers = dns.get("answers") or []
                    if query_name:
                        for ip in answers:
                            if ip:
                                dns_by_pid_ip[(pid, ip)].add(query_name)
                    continue

                if event_type == "unix_connect":
                    passthrough = dict(event)
                    passthrough["schema_version"] = schema_version
                    passthrough_rows.append((ts_dt, passthrough))
                    continue

                if event_type not in ("net_connect", "net_send"):
                    continue

                net = event.get("net") or event.get("details", {}).get("net") or {}
                dst_ip = net.get("dst_ip")
                dst_port = parse_int(net.get("dst_port"))
                if not dst_ip or dst_port is None:
                    continue
                if dst_port == 53:
                    continue

                session_id = event.get("session_id", "unknown")
                job_id = event.get("job_id")
                pid = parse_int(event.get("pid"))
                if pid is None:
                    continue

                key = (session_id, job_id, pid, dst_ip, dst_port)
                group = groups.get(key)
                if not group:
                    group = {
                        "session_id": session_id,
                        "job_id": job_id,
                        "pid": pid,
                        "ppid": parse_int(event.get("ppid")),
                        "uid": parse_int(event.get("uid")),
                        "gid": parse_int(event.get("gid")),
                        "comm": event.get("comm") or "",
                        "dst_ip": dst_ip,
                        "dst_port": dst_port,
                        "protocol": None,
                        "ts_first": ts_dt,
                        "ts_last": ts_dt,
                        "connect_attempts": 0,
                        "send_count": 0,
                        "bytes_sent_total": 0,
                    }
                    groups[key] = group
                else:
                    if group.get("comm") == "" and event.get("comm"):
                        group["comm"] = event.get("comm")
                    for key_name in ("ppid", "uid", "gid"):
                        if group.get(key_name) is None:
                            group[key_name] = parse_int(event.get(key_name))

                if ts_dt < group["ts_first"]:
                    group["ts_first"] = ts_dt
                if ts_dt > group["ts_last"]:
                    group["ts_last"] = ts_dt

                if event_type == "net_connect":
                    group["connect_attempts"] += 1
                    proto = protocol_candidate(net.get("protocol"))
                    if proto and not group["protocol"]:
                        group["protocol"] = proto
                elif event_type == "net_send":
                    group["send_count"] += 1
                    bytes_value = parse_int(net.get("bytes"))
                    if bytes_value:
                        group["bytes_sent_total"] += bytes_value
                    proto = protocol_candidate(net.get("protocol"))
                    if proto and not group["protocol"]:
                        group["protocol"] = proto

    rows: list[tuple[dt.datetime, dict]] = []
    for (session_id, job_id, pid, dst_ip, dst_port), group in groups.items():
        ts_first = group["ts_first"]
        ts_last = group["ts_last"]
        ts_first_str = format_ts(ts_first)
        ts_last_str = format_ts(ts_last)
        dns_names = sorted(dns_by_pid_ip.get((pid, dst_ip), set()))
        row = {
            "schema_version": schema_version,
            "session_id": session_id,
            "ts": ts_first_str,
            "source": "ebpf",
            "event_type": "net_summary",
            "pid": pid,
            "ppid": group.get("ppid"),
            "uid": group.get("uid"),
            "gid": group.get("gid"),
            "comm": group.get("comm") or "",
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "protocol": group.get("protocol") or "unknown",
            "dns_names": dns_names,
            "connect_attempts": group.get("connect_attempts", 0),
            "send_count": group.get("send_count", 0),
            "bytes_sent_total": group.get("bytes_sent_total", 0),
            "ts_first": ts_first_str,
            "ts_last": ts_last_str,
        }
        if job_id:
            row["job_id"] = job_id
        rows.append((ts_first, row))

    rows.extend(passthrough_rows)
    rows.sort(key=lambda item: item[0])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for _, row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    os.replace(tmp_path, output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
