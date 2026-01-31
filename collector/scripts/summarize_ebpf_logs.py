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


class SendEvent:
    __slots__ = ("ts", "bytes", "protocol", "comm", "ppid", "uid", "gid")

    def __init__(self, ts: dt.datetime, bytes_sent: int, protocol: str, comm: str, ppid: int | None, uid: int | None, gid: int | None) -> None:
        self.ts = ts
        self.bytes = bytes_sent
        self.protocol = protocol
        self.comm = comm
        self.ppid = ppid
        self.uid = uid
        self.gid = gid


class ConnectEvent:
    __slots__ = ("ts", "protocol")

    def __init__(self, ts: dt.datetime, protocol: str) -> None:
        self.ts = ts
        self.protocol = protocol


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize filtered eBPF logs into burst-level network rows.")
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
    burst_gap_sec = float(cfg.get("burst_gap_sec", 5))
    dns_lookback_sec = float(cfg.get("dns_lookback_sec", 2))
    min_send_count = int(cfg.get("min_send_count", 0))
    min_bytes_sent_total = int(cfg.get("min_bytes_sent_total", 0))
    if dns_lookback_sec < 0:
        dns_lookback_sec = 0

    dns_by_key: dict[tuple[str, int, str], list[tuple[dt.datetime, str]]] = defaultdict(list)
    sends_by_key: dict[tuple[str, str | None, int, str, int], list[SendEvent]] = defaultdict(list)
    connects_by_key: dict[tuple[str, str | None, int, str, int], list[ConnectEvent]] = defaultdict(list)
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
                    session_id = event.get("session_id", "unknown")
                    dns = event.get("dns") or event.get("details", {}).get("dns")
                    if pid is None or not isinstance(dns, dict):
                        continue
                    query_name = dns.get("query_name")
                    answers = dns.get("answers") or []
                    if query_name:
                        for ip in answers:
                            if ip:
                                dns_by_key[(session_id, pid, ip)].append((ts_dt, query_name))
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

                protocol = net.get("protocol") or "unknown"
                comm = event.get("comm") or ""
                ppid = parse_int(event.get("ppid"))
                uid = parse_int(event.get("uid"))
                gid = parse_int(event.get("gid"))

                if event_type == "net_connect":
                    connects_by_key[key].append(ConnectEvent(ts_dt, protocol))
                    continue

                bytes_sent = parse_int(net.get("bytes")) or 0
                sends_by_key[key].append(SendEvent(ts_dt, bytes_sent, protocol, comm, ppid, uid, gid))

    rows: list[tuple[dt.datetime, dict]] = []

    for key, send_events in sends_by_key.items():
        send_events.sort(key=lambda ev: ev.ts)
        session_id, job_id, pid, dst_ip, dst_port = key
        connects = connects_by_key.get(key, [])
        connects.sort(key=lambda ev: ev.ts)
        dns_entries = dns_by_key.get((session_id, pid, dst_ip), [])

        burst_start = send_events[0].ts
        burst_end = send_events[0].ts
        send_count = 0
        bytes_total = 0
        comm = send_events[0].comm
        ppid = send_events[0].ppid
        uid = send_events[0].uid
        gid = send_events[0].gid
        protocol = protocol_candidate(send_events[0].protocol)

        def finalize_burst(start: dt.datetime, end: dt.datetime, count: int, bytes_sum: int, proto: str | None) -> None:
            nonlocal rows
            if count <= min_send_count and bytes_sum <= min_bytes_sent_total:
                return
            window_start = start - dt.timedelta(seconds=dns_lookback_sec)
            dns_names = sorted({
                name
                for ts, name in dns_entries
                if window_start <= ts <= end
            })
            connect_count = sum(1 for conn in connects if start <= conn.ts <= end)
            chosen_protocol = proto
            if not chosen_protocol:
                for conn in connects:
                    if start <= conn.ts <= end:
                        candidate = protocol_candidate(conn.protocol)
                        if candidate:
                            chosen_protocol = candidate
                            break
            if not chosen_protocol:
                chosen_protocol = "unknown"

            row = {
                "schema_version": schema_version,
                "session_id": session_id,
                "ts": format_ts(start),
                "source": "ebpf",
                "event_type": "net_summary",
                "pid": pid,
                "ppid": ppid,
                "uid": uid,
                "gid": gid,
                "comm": comm or "",
                "dst_ip": dst_ip,
                "dst_port": dst_port,
                "protocol": chosen_protocol,
                "dns_names": dns_names,
                "connect_count": connect_count,
                "send_count": count,
                "bytes_sent_total": bytes_sum,
                "ts_first": format_ts(start),
                "ts_last": format_ts(end),
            }
            if job_id:
                row["job_id"] = job_id
            rows.append((start, row))

        last_ts: dt.datetime | None = None
        send_count = 0
        bytes_total = 0
        for ev in send_events:
            if last_ts is None:
                burst_start = ev.ts
                burst_end = ev.ts
            else:
                gap = (ev.ts - last_ts).total_seconds()
                if gap > burst_gap_sec:
                    finalize_burst(burst_start, burst_end, send_count, bytes_total, protocol)
                    burst_start = ev.ts
                    burst_end = ev.ts
                    send_count = 0
                    bytes_total = 0
                    protocol = None
                    comm = ev.comm
                    ppid = ev.ppid
                    uid = ev.uid
                    gid = ev.gid
            burst_end = ev.ts
            send_count += 1
            bytes_total += ev.bytes
            if not comm and ev.comm:
                comm = ev.comm
            if ppid is None and ev.ppid is not None:
                ppid = ev.ppid
            if uid is None and ev.uid is not None:
                uid = ev.uid
            if gid is None and ev.gid is not None:
                gid = ev.gid
            if protocol is None:
                protocol = protocol_candidate(ev.protocol)
            last_ts = ev.ts

        finalize_burst(burst_start, burst_end, send_count, bytes_total, protocol)

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
