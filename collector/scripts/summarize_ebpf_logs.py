#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import heapq
import json
import os
import time
from collections import defaultdict, deque
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


class BurstState:
    __slots__ = (
        "start_ts",
        "last_ts",
        "send_count",
        "bytes_total",
        "comm",
        "ppid",
        "uid",
        "gid",
        "protocol",
    )

    def __init__(
        self,
        ts: dt.datetime,
        bytes_sent: int,
        protocol: str | None,
        comm: str,
        ppid: int | None,
        uid: int | None,
        gid: int | None,
    ) -> None:
        self.start_ts = ts
        self.last_ts = ts
        self.send_count = 1
        self.bytes_total = bytes_sent
        self.comm = comm
        self.ppid = ppid
        self.uid = uid
        self.gid = gid
        self.protocol = protocol


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize filtered eBPF logs into burst-level network rows.")
    parser.add_argument(
        "--config",
        default=os.getenv("COLLECTOR_EBPF_SUMMARY_CONFIG", "/etc/collector/ebpf_summary.yaml"),
        help="Path to ebpf_summary.yaml",
    )
    parser.add_argument("--follow", action="store_true", help="Tail the eBPF summary input")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval for follow mode (seconds)",
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


def run_batch(cfg: dict) -> int:
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


def run_follow(cfg: dict, poll_interval: float) -> int:
    schema_version = cfg.get("schema_version", "ebpf.summary.v1")
    input_path = Path(cfg.get("input", {}).get("jsonl", "/logs/filtered_ebpf.jsonl"))
    output_path = Path(cfg.get("output", {}).get("jsonl", "/logs/filtered_ebpf_summary.jsonl"))
    burst_gap_sec = float(cfg.get("burst_gap_sec", 5))
    dns_lookback_sec = float(cfg.get("dns_lookback_sec", 2))
    min_send_count = int(cfg.get("min_send_count", 0))
    min_bytes_sent_total = int(cfg.get("min_bytes_sent_total", 0))
    max_late_sec = float(cfg.get("max_late_sec", max(burst_gap_sec, dns_lookback_sec, 1)))
    if dns_lookback_sec < 0:
        dns_lookback_sec = 0

    dns_by_key: dict[tuple[str, int, str], deque[tuple[dt.datetime, str]]] = defaultdict(deque)
    connects_by_key: dict[tuple[str, str | None, int, str, int], deque[ConnectEvent]] = defaultdict(deque)
    open_bursts: dict[tuple[str, str | None, int, str, int], BurstState] = {}
    pending: list[tuple[dt.datetime, str, int, int, dict]] = []
    pending_seq = 0
    last_event_ts: dt.datetime | None = None
    min_dt = dt.datetime.min.replace(tzinfo=dt.timezone.utc)

    def enqueue(ts_dt: dt.datetime, row: dict) -> None:
        nonlocal pending_seq
        pending_seq += 1
        heapq.heappush(
            pending,
            (
                ts_dt or min_dt,
                row.get("source") or "ebpf",
                row.get("pid") or 0,
                pending_seq,
                row,
            ),
        )

    def flush_ready(watermark: dt.datetime) -> None:
        while pending and pending[0][0] <= watermark:
            _, _, _, _, row = heapq.heappop(pending)
            writer.write(json.dumps(row, separators=(",", ":")) + "\n")
            writer.flush()

    def dns_prune_key(dns_key: tuple[str, int, str], now_ts: dt.datetime) -> None:
        entries = dns_by_key.get(dns_key)
        if not entries:
            return
        earliest_start = None
        for burst_key, burst in open_bursts.items():
            if (burst_key[0], burst_key[2], burst_key[3]) != dns_key:
                continue
            if earliest_start is None or burst.start_ts < earliest_start:
                earliest_start = burst.start_ts
        if earliest_start is None:
            cutoff = now_ts - dt.timedelta(seconds=dns_lookback_sec)
        else:
            cutoff = earliest_start - dt.timedelta(seconds=dns_lookback_sec)
        while entries and entries[0][0] < cutoff:
            entries.popleft()
        if not entries:
            dns_by_key.pop(dns_key, None)

    def connect_prune_key(key: tuple[str, str | None, int, str, int], now_ts: dt.datetime) -> None:
        entries = connects_by_key.get(key)
        if not entries:
            return
        burst = open_bursts.get(key)
        if burst:
            cutoff = burst.start_ts
        else:
            cutoff = now_ts - dt.timedelta(seconds=burst_gap_sec)
        while entries and entries[0].ts < cutoff:
            entries.popleft()
        if not entries:
            connects_by_key.pop(key, None)

    def finalize_burst(
        key: tuple[str, str | None, int, str, int],
        burst: BurstState,
    ) -> None:
        if burst.send_count <= min_send_count and burst.bytes_total <= min_bytes_sent_total:
            return
        session_id, job_id, pid, dst_ip, dst_port = key
        dns_entries = dns_by_key.get((session_id, pid, dst_ip), deque())
        connects = connects_by_key.get(key, deque())
        window_start = burst.start_ts - dt.timedelta(seconds=dns_lookback_sec)
        dns_names = sorted({
            name
            for ts, name in dns_entries
            if window_start <= ts <= burst.last_ts
        })
        connect_count = sum(1 for conn in connects if burst.start_ts <= conn.ts <= burst.last_ts)
        chosen_protocol = burst.protocol
        if not chosen_protocol:
            for conn in connects:
                if burst.start_ts <= conn.ts <= burst.last_ts:
                    candidate = protocol_candidate(conn.protocol)
                    if candidate:
                        chosen_protocol = candidate
                        break
        if not chosen_protocol:
            chosen_protocol = "unknown"
        row = {
            "schema_version": schema_version,
            "session_id": session_id,
            "ts": format_ts(burst.start_ts),
            "source": "ebpf",
            "event_type": "net_summary",
            "pid": pid,
            "ppid": burst.ppid,
            "uid": burst.uid,
            "gid": burst.gid,
            "comm": burst.comm or "",
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "protocol": chosen_protocol,
            "dns_names": dns_names,
            "connect_count": connect_count,
            "send_count": burst.send_count,
            "bytes_sent_total": burst.bytes_total,
            "ts_first": format_ts(burst.start_ts),
            "ts_last": format_ts(burst.last_ts),
        }
        if job_id:
            row["job_id"] = job_id
        enqueue(burst.start_ts, row)

    def finalize_idle(now_ts: dt.datetime, force_all: bool = False) -> None:
        cutoff = now_ts - dt.timedelta(seconds=burst_gap_sec)
        for key, burst in list(open_bursts.items()):
            if force_all or burst.last_ts <= cutoff:
                finalize_burst(key, burst)
                open_bursts.pop(key, None)
                connect_prune_key(key, now_ts)
                dns_prune_key((key[0], key[2], key[3]), now_ts)

    def process_event(event: dict, ts_dt: dt.datetime) -> None:
        nonlocal last_event_ts
        if last_event_ts is None or ts_dt > last_event_ts:
            last_event_ts = ts_dt

        event_type = event.get("event_type")
        if event_type == "dns_response":
            pid = parse_int(event.get("pid"))
            session_id = event.get("session_id", "unknown")
            dns = event.get("dns") or event.get("details", {}).get("dns")
            if pid is None or not isinstance(dns, dict):
                return
            query_name = dns.get("query_name")
            answers = dns.get("answers") or []
            if query_name:
                for ip in answers:
                    if ip:
                        dns_by_key[(session_id, pid, ip)].append((ts_dt, query_name))
                        dns_prune_key((session_id, pid, ip), ts_dt)
            return

        if event_type == "unix_connect":
            passthrough = dict(event)
            passthrough["schema_version"] = schema_version
            enqueue(ts_dt, passthrough)
            return

        if event_type not in ("net_connect", "net_send"):
            return

        net = event.get("net") or event.get("details", {}).get("net") or {}
        dst_ip = net.get("dst_ip")
        dst_port = parse_int(net.get("dst_port"))
        if not dst_ip or dst_port is None:
            return
        if dst_port == 53:
            return

        session_id = event.get("session_id", "unknown")
        job_id = event.get("job_id")
        pid = parse_int(event.get("pid"))
        if pid is None:
            return

        key = (session_id, job_id, pid, dst_ip, dst_port)
        protocol = net.get("protocol") or "unknown"
        comm = event.get("comm") or ""
        ppid = parse_int(event.get("ppid"))
        uid = parse_int(event.get("uid"))
        gid = parse_int(event.get("gid"))

        if event_type == "net_connect":
            connects_by_key[key].append(ConnectEvent(ts_dt, protocol))
            connect_prune_key(key, ts_dt)
            return

        bytes_sent = parse_int(net.get("bytes")) or 0
        burst = open_bursts.get(key)
        if burst is None:
            open_bursts[key] = BurstState(
                ts_dt,
                bytes_sent,
                protocol_candidate(protocol),
                comm,
                ppid,
                uid,
                gid,
            )
            return

        gap = (ts_dt - burst.last_ts).total_seconds()
        if gap > burst_gap_sec:
            finalize_burst(key, burst)
            open_bursts[key] = BurstState(
                ts_dt,
                bytes_sent,
                protocol_candidate(protocol),
                comm,
                ppid,
                uid,
                gid,
            )
            return

        burst.last_ts = ts_dt
        burst.send_count += 1
        burst.bytes_total += bytes_sent
        if not burst.comm and comm:
            burst.comm = comm
        if burst.ppid is None and ppid is not None:
            burst.ppid = ppid
        if burst.uid is None and uid is not None:
            burst.uid = uid
        if burst.gid is None and gid is not None:
            burst.gid = gid
        if burst.protocol is None:
            burst.protocol = protocol_candidate(protocol)

    def iter_follow_lines(path: Path, interval: float):
        position = 0
        inode = None
        handle = None

        def reopen():
            nonlocal handle, position, inode
            if handle:
                handle.close()
            handle = open(path, "r", encoding="utf-8", errors="replace")
            stat = os.fstat(handle.fileno())
            inode = stat.st_ino
            handle.seek(0, os.SEEK_SET)
            position = handle.tell()

        while True:
            try:
                reopen()
                break
            except FileNotFoundError:
                time.sleep(interval)

        while True:
            line = handle.readline()
            if line:
                position = handle.tell()
                yield ("line", line)
                continue
            time.sleep(interval)
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                yield ("idle", None)
                continue
            if inode is None or stat.st_ino != inode:
                reopen()
                yield ("reset", None)
                continue
            if stat.st_size < position:
                reopen()
                yield ("reset", None)
                continue
            yield ("idle", None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_idle_check = time.monotonic()
    with output_path.open("a", encoding="utf-8") as writer:
        for kind, line in iter_follow_lines(input_path, poll_interval):
            if kind == "reset":
                now_ts = dt.datetime.now(dt.timezone.utc)
                finalize_idle(now_ts, force_all=True)
                flush_ready(now_ts)
                open_bursts.clear()
                connects_by_key.clear()
                dns_by_key.clear()
                continue
            if kind == "idle":
                now_ts = dt.datetime.now(dt.timezone.utc)
                finalize_idle(now_ts)
                watermark = now_ts - dt.timedelta(seconds=max_late_sec)
                flush_ready(watermark)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_dt = parse_ts(event.get("ts"))
            if ts_dt is None:
                continue
            process_event(event, ts_dt)
            now_mono = time.monotonic()
            if now_mono - last_idle_check >= poll_interval:
                now_ts = dt.datetime.now(dt.timezone.utc)
                finalize_idle(now_ts)
                last_idle_check = now_mono
            watermark = (last_event_ts or ts_dt) - dt.timedelta(seconds=max_late_sec)
            flush_ready(watermark)

    return 0


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    if args.follow:
        return run_follow(cfg, args.poll_interval)
    return run_batch(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
