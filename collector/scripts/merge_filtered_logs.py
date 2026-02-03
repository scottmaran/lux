#!/usr/bin/env python3
import argparse
import datetime as dt
import heapq
import json
import os
import sys
import time

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
    parser.add_argument("--follow", action="store_true", help="Tail inputs and append to output")
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


def run_batch(cfg: dict) -> int:
    schema_version = cfg.get("schema_version", "timeline.filtered.v1")

    inputs = cfg.get("inputs", [])
    output_path = cfg.get("output", {}).get("jsonl", "/logs/filtered_timeline.jsonl")
    sort_strategy = cfg.get("sorting", {}).get("strategy", "ts_source_pid")

    rows = []
    for source_cfg in inputs:
        path = source_cfg.get("path")
        if not path or not os.path.exists(path):
            continue
        source_default = source_cfg.get("source") or ""
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


class InputTail:
    def __init__(self, path: str, source_default: str) -> None:
        self.path = path
        self.source_default = source_default
        self.handle = None
        self.inode = None
        self.position = 0
        self.start_time = time.monotonic()
        self.last_read_time = self.start_time
        self.last_event_ts: dt.datetime | None = None

    def _open(self) -> bool:
        try:
            self.handle = open(self.path, "r", encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return False
        stat = os.fstat(self.handle.fileno())
        self.inode = stat.st_ino
        self.handle.seek(0, os.SEEK_SET)
        self.position = self.handle.tell()
        self.last_read_time = time.monotonic()
        return True

    def _close(self) -> None:
        if self.handle:
            self.handle.close()
        self.handle = None
        self.inode = None
        self.position = 0

    def read_lines(self) -> list[str]:
        if self.handle is None and not self._open():
            return []
        assert self.handle is not None
        try:
            stat = os.stat(self.path)
        except FileNotFoundError:
            self._close()
            return []
        if self.inode is None or stat.st_ino != self.inode or stat.st_size < self.position:
            self._close()
            self.last_event_ts = None
            if not self._open():
                return []
        lines = []
        while True:
            line = self.handle.readline()
            if not line:
                break
            self.position = self.handle.tell()
            lines.append(line)
        if lines:
            self.last_read_time = time.monotonic()
        return lines


def run_follow(cfg: dict, poll_interval: float) -> int:
    schema_version = cfg.get("schema_version", "timeline.filtered.v1")
    inputs_cfg = cfg.get("inputs", [])
    output_path = cfg.get("output", {}).get("jsonl", "/logs/filtered_timeline.jsonl")
    max_late_sec = float(cfg.get("max_late_sec", 10))
    idle_flush_sec = float(cfg.get("idle_flush_sec", 5))
    startup_grace_sec = float(cfg.get("startup_grace_sec", 2))
    max_buffer_rows = int(cfg.get("max_buffer_rows", 5000))

    tails = []
    for source_cfg in inputs_cfg:
        path = source_cfg.get("path")
        if not path:
            continue
        source_default = source_cfg.get("source") or ""
        tails.append(InputTail(path, source_default))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    min_dt = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    heap: list[tuple[dt.datetime, str, int, int, dict]] = []
    heap_seq = 0
    last_emitted_ts: dt.datetime | None = None

    def push_event(ts_dt: dt.datetime | None, row: dict) -> None:
        nonlocal heap_seq
        heap_seq += 1
        heapq.heappush(
            heap,
            (
                ts_dt or min_dt,
                row.get("source") or "",
                row.get("pid") or 0,
                heap_seq,
                row,
            ),
        )

    def compute_watermark(now_ts: dt.datetime, now_mono: float) -> dt.datetime | None:
        watermarks = []
        for tail in tails:
            if tail.last_event_ts is None:
                if now_mono - tail.start_time < startup_grace_sec:
                    return None
                watermarks.append(now_ts - dt.timedelta(seconds=max_late_sec))
                continue
            if now_mono - tail.last_read_time >= idle_flush_sec:
                watermarks.append(now_ts - dt.timedelta(seconds=max_late_sec))
            else:
                watermarks.append(tail.last_event_ts - dt.timedelta(seconds=max_late_sec))
        if not watermarks:
            return now_ts - dt.timedelta(seconds=max_late_sec)
        return min(watermarks)

    with open(output_path, "a", encoding="utf-8") as writer:
        while True:
            any_lines = False
            for tail in tails:
                lines = tail.read_lines()
                if not lines:
                    continue
                any_lines = True
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    normalized = normalize_event(event, tail.source_default, schema_version)
                    ts_dt = parse_ts(normalized.get("ts"))
                    if ts_dt and (tail.last_event_ts is None or ts_dt > tail.last_event_ts):
                        tail.last_event_ts = ts_dt
                    push_event(ts_dt, normalized)

            now_ts = dt.datetime.now(dt.timezone.utc)
            now_mono = time.monotonic()
            watermark = compute_watermark(now_ts, now_mono)
            if watermark is None:
                if len(heap) > max_buffer_rows:
                    watermark = heap[0][0]
                else:
                    time.sleep(poll_interval)
                    continue

            while heap and heap[0][0] <= watermark:
                ts_dt, _, _, _, row = heapq.heappop(heap)
                if last_emitted_ts and ts_dt < last_emitted_ts:
                    # Late event; emit anyway to avoid blocking.
                    pass
                writer.write(json.dumps(row, separators=(",", ":")) + "\n")
                writer.flush()
                last_emitted_ts = ts_dt

            if not any_lines:
                time.sleep(poll_interval)

    return 0


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    if args.follow:
        return run_follow(cfg, args.poll_interval)
    return run_batch(cfg)


if __name__ == "__main__":
    sys.exit(main())
