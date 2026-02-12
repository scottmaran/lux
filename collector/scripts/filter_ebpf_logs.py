#!/usr/bin/env python3
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import shlex
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

try:
    import yaml
except ImportError:
    yaml = None


MSG_RE = re.compile(r"audit\((\d+)\.(\d+):(\d+)\)")
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter eBPF logs into JSONL.")
    parser.add_argument(
        "--config",
        default=os.getenv("COLLECTOR_EBPF_FILTER_CONFIG", "/etc/collector/ebpf_filtering.yaml"),
        help="Path to ebpf_filtering.yaml",
    )
    parser.add_argument("--follow", action="store_true", help="Tail the eBPF log")
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
        raise SystemExit(
            "collector-ebpf-filter: missing PyYAML and config is not valid JSON"
        ) from exc


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_msg(msg: str) -> tuple[int, dt.datetime, str] | tuple[None, None, None]:
    match = MSG_RE.search(msg)
    if not match:
        return None, None, None
    sec = int(match.group(1))
    sub = match.group(2)
    seq = int(match.group(3))
    micros = int((sub + "000000")[:6])
    ts = dt.datetime.fromtimestamp(sec, tz=dt.timezone.utc) + dt.timedelta(microseconds=micros)
    ts_iso = ts.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return seq, ts, ts_iso


def parse_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError:
        tokens = line.split()
    fields = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    record_type = fields.get("type")
    msg = fields.get("msg")
    if not record_type or not msg:
        return None
    seq, ts, ts_iso = parse_msg(msg)
    if seq is None:
        return None
    return {"type": record_type, "seq": seq, "ts": ts, "ts_iso": ts_iso, "fields": fields}


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def sanitize_key(value: str | None) -> str | None:
    if not value or value == "(null)":
        return None
    return value


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if 32 <= ord(ch) <= 126 or ch in "\t\n\r")
    return printable / len(text)


def decode_execve_arg(value: str) -> str:
    if not value or value == "(null)":
        return ""
    if HEX_RE.match(value) and len(value) % 2 == 0:
        try:
            decoded = bytes.fromhex(value).decode("utf-8", errors="replace")
            if printable_ratio(decoded) >= 0.85:
                return decoded
        except ValueError:
            pass
    return value


def parse_execve_args(records: list[dict]) -> list[str]:
    args = {}
    for record in records:
        for key, value in record["fields"].items():
            if key.startswith("a") and key[1:].isdigit():
                idx = int(key[1:])
                args[idx] = decode_execve_arg(value)
    return [args[idx] for idx in sorted(args)]


def derive_cmd(argv: list[str], comm: str, shell_comm: set[str], shell_flag: str) -> str:
    if not argv:
        return comm or ""
    if comm in shell_comm and shell_flag in argv:
        flag_index = argv.index(shell_flag)
        if flag_index + 1 < len(argv):
            return argv[flag_index + 1]
    return shlex.join(argv)


def parse_ebpf_ts(ts: str | None) -> dt.datetime | None:
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


def extract_exec(records: list[dict], cfg: dict) -> dict | None:
    syscall = next((r for r in records if r["type"] == "SYSCALL"), None)
    if not syscall:
        return None
    audit_key = sanitize_key(syscall["fields"].get("key"))
    exec_keys = set(cfg.get("ownership", {}).get("exec_keys", ["exec"]))
    if audit_key not in exec_keys:
        return None
    pid = parse_int(syscall["fields"].get("pid"))
    ppid = parse_int(syscall["fields"].get("ppid"))
    uid = parse_int(syscall["fields"].get("uid"))
    comm = syscall["fields"].get("comm") or ""
    ts = syscall["ts"]
    if ts is None:
        return None
    exec_cfg = cfg.get("exec", {})
    shell_comm = set(exec_cfg.get("shell_comm", ["bash", "sh"]))
    shell_flag = exec_cfg.get("shell_cmd_flag", "-lc")
    exec_records = [r for r in records if r["type"] == "EXECVE"]
    argv = parse_execve_args(exec_records)
    cmd = derive_cmd(argv, comm, shell_comm, shell_flag)
    return {"pid": pid, "ppid": ppid, "uid": uid, "comm": comm, "ts": ts, "cmd": cmd}


def load_session_roots(sessions_dir: str) -> tuple[dict[int, str], dict[int, str]]:
    roots_by_pid: dict[int, str] = {}
    roots_by_sid: dict[int, str] = {}
    if not sessions_dir or not os.path.isdir(sessions_dir):
        return roots_by_pid, roots_by_sid
    for entry in os.scandir(sessions_dir):
        if not entry.is_dir():
            continue
        meta_path = os.path.join(entry.path, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as handle:
                meta = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        session_id = meta.get("session_id") or entry.name
        root_pid = parse_int(meta.get("root_pid"))
        if root_pid is not None:
            roots_by_pid[root_pid] = session_id
        root_sid = parse_int(meta.get("root_sid"))
        if root_sid is not None:
            roots_by_sid[root_sid] = session_id
    return roots_by_pid, roots_by_sid


def load_job_roots(jobs_dir: str) -> tuple[dict[int, str], dict[int, str]]:
    roots_by_pid: dict[int, str] = {}
    roots_by_sid: dict[int, str] = {}
    if not jobs_dir or not os.path.isdir(jobs_dir):
        return roots_by_pid, roots_by_sid
    for entry in os.scandir(jobs_dir):
        if not entry.is_dir():
            continue
        input_path = os.path.join(entry.path, "input.json")
        status_path = os.path.join(entry.path, "status.json")
        meta = {}
        status = {}
        if os.path.isfile(input_path):
            try:
                with open(input_path, "r", encoding="utf-8") as handle:
                    meta = json.load(handle)
            except (OSError, json.JSONDecodeError):
                meta = {}
        if os.path.isfile(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as handle:
                    status = json.load(handle)
            except (OSError, json.JSONDecodeError):
                status = {}
        job_id = meta.get("job_id") or status.get("job_id") or entry.name
        root_pid = parse_int(meta.get("root_pid"))
        if root_pid is None:
            root_pid = parse_int(status.get("root_pid"))
        if root_pid is not None:
            roots_by_pid[root_pid] = job_id
        root_sid = parse_int(meta.get("root_sid"))
        if root_sid is None:
            root_sid = parse_int(status.get("root_sid"))
        if root_sid is not None:
            roots_by_sid[root_sid] = job_id
    return roots_by_pid, roots_by_sid


class RunIndex:
    def __init__(self, sessions_dir: str, jobs_dir: str, refresh_sec: float = 1.0):
        self.sessions_dir = sessions_dir
        self.jobs_dir = jobs_dir
        self.refresh_sec = refresh_sec
        self.session_roots: dict[int, str] = {}
        self.session_sids: dict[int, str] = {}
        self.job_roots: dict[int, str] = {}
        self.job_sids: dict[int, str] = {}
        self.root_pids: set[int] = set()
        self.root_sids: set[int] = set()
        self.last_refresh = 0.0

    def _refresh(self) -> None:
        self.session_roots, self.session_sids = load_session_roots(self.sessions_dir)
        self.job_roots, self.job_sids = load_job_roots(self.jobs_dir)
        self.root_pids = set(self.session_roots) | set(self.job_roots)
        self.root_sids = set(self.session_sids) | set(self.job_sids)
        self.last_refresh = time.time()

    def maybe_refresh(self) -> None:
        now = time.time()
        if now - self.last_refresh < self.refresh_sec:
            return
        self._refresh()

    def force_refresh(self) -> None:
        self._refresh()


@dataclass
class AuditCursor:
    inode: int | None
    offset: int


class OwnershipState:
    def __init__(self, ttl_sec: int | float = 0) -> None:
        self.owned_pids: dict[int, dt.datetime] = {}
        self.last_exec_by_pid: dict[int, str] = {}
        self.pid_to_session: dict[int, str | None] = {}
        self.pid_to_job: dict[int, str | None] = {}
        self.ns_pid_cache: dict[int, int] = {}
        self.ns_sid_cache: dict[int, int] = {}
        self.ttl_sec = ttl_sec

    def _prune(self, now: dt.datetime) -> None:
        if not self.ttl_sec:
            return
        cutoff = now - dt.timedelta(seconds=self.ttl_sec)
        stale = [pid for pid, ts in self.owned_pids.items() if ts < cutoff]
        for pid in stale:
            self.owned_pids.pop(pid, None)
            self.last_exec_by_pid.pop(pid, None)
            self.pid_to_session.pop(pid, None)
            self.pid_to_job.pop(pid, None)
            self.ns_pid_cache.pop(pid, None)
            self.ns_sid_cache.pop(pid, None)

    def ns_pid(self, pid: int | None) -> int | None:
        if pid is None:
            return None
        cached = self.ns_pid_cache.get(pid)
        if cached is not None:
            return cached
        ns_pid = pid
        try:
            with open(f"/proc/{pid}/status", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("NSpid:"):
                        parts = line.split()
                        if len(parts) > 1 and parts[-1].isdigit():
                            ns_pid = int(parts[-1])
                        break
        except OSError:
            ns_pid = pid
        self.ns_pid_cache[pid] = ns_pid
        return ns_pid

    def ns_sid(self, pid: int | None) -> int | None:
        if pid is None:
            return None
        cached = self.ns_sid_cache.get(pid)
        if cached is not None:
            return cached
        sid = None
        try:
            with open(f"/proc/{pid}/status", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("NSsid:"):
                        parts = line.split()
                        if len(parts) > 1 and parts[-1].isdigit():
                            sid = int(parts[-1])
                        break
        except OSError:
            sid = None
        if sid is None:
            sid = pid
        self.ns_sid_cache[pid] = sid
        return sid

    def is_owned(
        self,
        pid: int | None,
        now: dt.datetime | None = None,
        root_pids: set[int] | None = None,
    ) -> bool:
        if pid is None:
            return False
        if now:
            self._prune(now)
        if pid in self.owned_pids:
            return True
        if root_pids and pid in root_pids:
            if now:
                self.owned_pids[pid] = now
            return True
        return False

    def mark_owned(
        self,
        pid: int | None,
        ppid: int | None,
        uid: int | None,
        comm: str,
        agent_uid: int | None,
        root_comm: set[str],
        ts: dt.datetime,
        root_pids: set[int] | None = None,
        cmd: str | None = None,
    ) -> bool:
        if pid is None:
            return False
        self._prune(ts)
        if root_pids and pid in root_pids:
            self.owned_pids[pid] = ts
            if cmd:
                self.last_exec_by_pid[pid] = cmd
            return True
        if ppid is not None and (ppid in self.owned_pids or (root_pids and ppid in root_pids)):
            self.owned_pids[pid] = ts
            if cmd:
                self.last_exec_by_pid[pid] = cmd
            return True
        if agent_uid is None or uid is None or uid != agent_uid:
            return False
        if root_comm and comm not in root_comm:
            return False
        self.owned_pids[pid] = ts
        if cmd:
            self.last_exec_by_pid[pid] = cmd
        return True

    def assign_run(
        self,
        pid: int | None,
        ppid: int | None,
        sid: int | None,
        run_index: "RunIndex",
    ) -> tuple[str | None, str | None]:
        if pid is None and sid is None:
            return None, None
        if pid is not None and (pid in self.pid_to_session or pid in self.pid_to_job):
            return self.pid_to_session.get(pid), self.pid_to_job.get(pid)
        run_index.maybe_refresh()
        if pid is not None:
            session_id = run_index.session_roots.get(pid)
            if session_id:
                self.pid_to_session[pid] = session_id
                self.pid_to_job[pid] = None
                return session_id, None
            job_id = run_index.job_roots.get(pid)
            if job_id:
                self.pid_to_session[pid] = None
                self.pid_to_job[pid] = job_id
                return None, job_id
        if ppid is not None:
            if ppid in self.pid_to_session or ppid in self.pid_to_job:
                session_id = self.pid_to_session.get(ppid)
                job_id = self.pid_to_job.get(ppid)
                if pid is not None:
                    self.pid_to_session[pid] = session_id
                    self.pid_to_job[pid] = job_id
                return session_id, job_id
            session_id = run_index.session_roots.get(ppid)
            if session_id:
                self.pid_to_session[ppid] = session_id
                self.pid_to_job[ppid] = None
                if pid is not None:
                    self.pid_to_session[pid] = session_id
                    self.pid_to_job[pid] = None
                return session_id, None
            job_id = run_index.job_roots.get(ppid)
            if job_id:
                self.pid_to_session[ppid] = None
                self.pid_to_job[ppid] = job_id
                if pid is not None:
                    self.pid_to_session[pid] = None
                    self.pid_to_job[pid] = job_id
                return None, job_id
        if sid is not None:
            session_id = run_index.session_sids.get(sid)
            if session_id:
                if pid is not None:
                    self.pid_to_session[pid] = session_id
                    self.pid_to_job[pid] = None
                return session_id, None
            job_id = run_index.job_sids.get(sid)
            if job_id:
                if pid is not None:
                    self.pid_to_session[pid] = None
                    self.pid_to_job[pid] = job_id
                return None, job_id
        return None, None


def build_ownership(
    audit_log: str,
    cfg: dict,
    run_index: RunIndex,
) -> tuple[OwnershipState, AuditCursor | None]:
    state = OwnershipState(cfg.get("ownership", {}).get("pid_ttl_sec", 0))
    agent_uid = cfg.get("ownership", {}).get("uid")
    root_comm = set(cfg.get("ownership", {}).get("root_comm", []))

    current_seq = None
    current_records: list[dict] = []
    cursor = None

    def flush(records: list[dict]) -> None:
        exec_info = extract_exec(records, cfg)
        if not exec_info:
            return
        run_index.maybe_refresh()
        ns_pid = state.ns_pid(exec_info["pid"])
        ns_ppid = state.ns_pid(exec_info["ppid"])
        ns_sid = state.ns_sid(exec_info["pid"])
        state.mark_owned(
            ns_pid,
            ns_ppid,
            exec_info["uid"],
            exec_info["comm"],
            agent_uid,
            root_comm,
            exec_info["ts"],
            root_pids=run_index.root_pids,
            cmd=exec_info["cmd"],
        )
        state.assign_run(ns_pid, ns_ppid, ns_sid, run_index)

    try:
        handle = open(audit_log, "r", encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return state, None

    with handle:
        stat = os.fstat(handle.fileno())
        inode = stat.st_ino
        for line in handle:
            record = parse_line(line)
            if not record:
                continue
            seq = record["seq"]
            if current_seq is None:
                current_seq = seq
            if seq != current_seq:
                flush(current_records)
                current_records = [record]
                current_seq = seq
            else:
                current_records.append(record)
        if current_records:
            flush(current_records)
        cursor = AuditCursor(inode=inode, offset=handle.tell())
    return state, cursor


def iter_file(
    path: str,
    follow: bool,
    poll_interval: float,
    start_at_end: bool = False,
    start_offset: int | None = None,
    start_inode: int | None = None,
    yield_idle: bool = False,
):
    position = 0
    inode = None
    handle = None

    def reopen(initial: bool):
        nonlocal handle, position, inode
        if handle:
            handle.close()
        handle = open(path, "r", encoding="utf-8", errors="replace")
        stat = os.fstat(handle.fileno())
        inode = stat.st_ino
        if initial:
            seek_pos = 0
            if start_inode is not None and inode != start_inode:
                seek_pos = 0
            elif start_offset is not None:
                if stat.st_size < start_offset:
                    seek_pos = 0
                else:
                    seek_pos = start_offset
            elif start_at_end:
                seek_pos = stat.st_size
            handle.seek(seek_pos, os.SEEK_SET)
        else:
            handle.seek(0, os.SEEK_SET)
        position = handle.tell()

    while True:
        try:
            reopen(True)
            break
        except FileNotFoundError:
            if not follow:
                return
            time.sleep(poll_interval)

    while True:
        line = handle.readline()
        if line:
            position = handle.tell()
            yield line
            continue
        if not follow:
            break
        if yield_idle:
            yield None
        time.sleep(poll_interval)
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            continue
        if inode is None or stat.st_ino != inode:
            reopen(False)
            continue
        if stat.st_size < position:
            reopen(False)


def write_output(writer, output: dict, write_lock: threading.Lock) -> None:
    if output is None:
        return
    encoded = json.dumps(output, separators=(",", ":")) + "\n"
    with write_lock:
        writer.write(encoded)
        writer.flush()


def follow_audit_log(
    audit_log: str,
    cfg: dict,
    state: OwnershipState,
    state_lock: threading.Lock,
    pending: PendingBuffer | None,
    pending_lock: threading.Lock,
    writer,
    write_lock: threading.Lock,
    run_index: RunIndex,
    link_cmd: bool,
    poll_interval: float,
    start_offset: int | None,
    start_inode: int | None,
) -> None:
    agent_uid = cfg.get("ownership", {}).get("uid")
    root_comm = set(cfg.get("ownership", {}).get("root_comm", []))
    schema_version = cfg.get("schema_version", "ebpf.filtered.v1")

    current_seq = None
    current_records: list[dict] = []
    last_line_time = time.monotonic()
    idle_flush_after = max(poll_interval * 4, 0.2)

    def flush(records: list[dict]) -> None:
        exec_info = extract_exec(records, cfg)
        if not exec_info:
            return
        pid = exec_info["pid"]
        if pid is None:
            return
        ts = exec_info["ts"]
        if ts is None:
            return
        with state_lock:
            run_index.maybe_refresh()
            ns_pid = state.ns_pid(pid)
            ns_ppid = state.ns_pid(exec_info["ppid"])
            ns_sid = state.ns_sid(pid)
            was_owned = state.is_owned(ns_pid, now=ts, root_pids=run_index.root_pids)
            owned = state.mark_owned(
                ns_pid,
                ns_ppid,
                exec_info["uid"],
                exec_info["comm"],
                agent_uid,
                root_comm,
                ts,
                root_pids=run_index.root_pids,
                cmd=exec_info["cmd"],
            )
            state.assign_run(ns_pid, ns_ppid, ns_sid, run_index)
            newly_owned = owned and not was_owned
        if not newly_owned or not pending:
            return
        with pending_lock:
            buffered = pending.pop(ns_pid, now=ts)
        if not buffered:
            return
        with state_lock:
            cmd = state.last_exec_by_pid.get(ns_pid) if link_cmd else None
        for item in buffered:
            with state_lock:
                session_id, job_id = state.assign_run(
                    item.event.get("_ns_pid"),
                    item.event.get("_ns_ppid"),
                    item.event.get("_ns_sid"),
                    run_index,
                )
            output = build_output(item.event, session_id or "unknown", job_id, cmd, schema_version)
            write_output(writer, output, write_lock)

    for line in iter_file(
        audit_log,
        follow=True,
        poll_interval=poll_interval,
        start_at_end=False,
        start_offset=start_offset,
        start_inode=start_inode,
        yield_idle=True,
    ):
        if line is None:
            if current_records and (time.monotonic() - last_line_time) >= idle_flush_after:
                flush(current_records)
                current_records = []
                current_seq = None
            continue
        record = parse_line(line)
        if not record:
            continue
        last_line_time = time.monotonic()
        seq = record["seq"]
        if current_seq is None:
            current_seq = seq
        if seq != current_seq:
            flush(current_records)
            current_records = [record]
            current_seq = seq
        else:
            current_records.append(record)


@dataclass
class PendingEvent:
    ts: dt.datetime
    event: dict


class PendingBuffer:
    def __init__(self, ttl_sec: float, max_per_pid: int, max_total: int):
        self.ttl = dt.timedelta(seconds=ttl_sec) if ttl_sec else None
        self.max_per_pid = max_per_pid
        self.max_total = max_total
        self.by_pid: dict[int, deque[PendingEvent]] = {}
        self.total = 0

    def _prune_pid(self, pid: int, now: dt.datetime) -> None:
        if not self.ttl:
            return
        queue = self.by_pid.get(pid)
        if not queue:
            return
        while queue and now - queue[0].ts > self.ttl:
            queue.popleft()
            self.total -= 1
        if not queue:
            self.by_pid.pop(pid, None)

    def _drop_oldest_until_under(self) -> None:
        while self.max_total and self.total > self.max_total and self.by_pid:
            oldest_pid = min(self.by_pid.items(), key=lambda item: item[1][0].ts)[0]
            queue = self.by_pid[oldest_pid]
            queue.popleft()
            self.total -= 1
            if not queue:
                self.by_pid.pop(oldest_pid, None)

    def add(self, pid: int, ts: dt.datetime, event: dict) -> None:
        self._prune_pid(pid, ts)
        queue = self.by_pid.setdefault(pid, deque())
        queue.append(PendingEvent(ts=ts, event=event))
        self.total += 1
        if self.max_per_pid and len(queue) > self.max_per_pid:
            while len(queue) > self.max_per_pid:
                queue.popleft()
                self.total -= 1
        self._drop_oldest_until_under()

    def pop(self, pid: int, now: dt.datetime) -> list[PendingEvent]:
        self._prune_pid(pid, now)
        queue = self.by_pid.pop(pid, None)
        if not queue:
            return []
        self.total -= len(queue)
        return list(queue)


def build_output(
    event: dict,
    session_id: str,
    job_id: str | None,
    cmd: str | None,
    schema_version: str,
) -> dict:
    output = {
        "schema_version": schema_version,
        "session_id": session_id,
        "ts": event.get("ts"),
        "source": "ebpf",
        "event_type": event.get("event_type"),
        "pid": event.get("pid"),
        "ppid": event.get("ppid"),
        "uid": event.get("uid"),
        "gid": event.get("gid"),
        "comm": event.get("comm") or "",
        "cgroup_id": event.get("cgroup_id"),
        "syscall_result": event.get("syscall_result"),
        "agent_owned": True,
    }
    if job_id:
        output["job_id"] = job_id
    if cmd:
        output["cmd"] = cmd
    event_type = event.get("event_type")
    if event_type in ("net_connect", "net_send") and event.get("net") is not None:
        output["net"] = event.get("net")
    if event_type in ("dns_query", "dns_response") and event.get("dns") is not None:
        output["dns"] = event.get("dns")
    if event_type == "unix_connect" and event.get("unix") is not None:
        output["unix"] = event.get("unix")
    return output


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    audit_log = os.getenv("COLLECTOR_AUDIT_LOG") or cfg.get("input", {}).get("audit_log", "/logs/audit.log")
    ebpf_log = os.getenv("COLLECTOR_EBPF_LOG") or cfg.get("input", {}).get("ebpf_log", "/logs/ebpf.jsonl")
    output_path = os.getenv("COLLECTOR_EBPF_FILTER_OUTPUT") or cfg.get("output", {}).get(
        "jsonl", "/logs/filtered_ebpf.jsonl"
    )
    sessions_dir = os.getenv("COLLECTOR_SESSIONS_DIR") or cfg.get("sessions_dir", "/logs/sessions")
    jobs_dir = os.getenv("COLLECTOR_JOBS_DIR") or cfg.get("jobs_dir", "/logs/jobs")

    include_types = set(cfg.get("include", {}).get("event_types", []))
    exclude_comm = set(cfg.get("exclude", {}).get("comm", []))
    exclude_unix_paths = set(cfg.get("exclude", {}).get("unix_paths", []))
    exclude_net_ports = set(cfg.get("exclude", {}).get("net_dst_ports", []))
    exclude_net_ips = set(cfg.get("exclude", {}).get("net_dst_ips", []))

    link_cmd = cfg.get("linking", {}).get("attach_cmd_to_net", False)

    run_index = RunIndex(sessions_dir, jobs_dir)
    state, audit_cursor = build_ownership(audit_log, cfg, run_index)
    state_lock = threading.Lock()
    pending_lock = threading.Lock()
    write_lock = threading.Lock()

    pending_cfg = cfg.get("pending_buffer", {})
    pending_enabled = pending_cfg.get("enabled")
    if pending_enabled is None:
        pending_enabled = any(
            key in pending_cfg for key in ("ttl_sec", "max_per_pid", "max_total")
        )
    if not args.follow:
        pending_enabled = False
    pending = None
    if pending_enabled:
        ttl_sec = float(pending_cfg.get("ttl_sec", 1.5))
        max_per_pid = int(pending_cfg.get("max_per_pid", 200))
        max_total = int(pending_cfg.get("max_total", 2000))
        if ttl_sec <= 0:
            pending_enabled = False
        else:
            pending = PendingBuffer(ttl_sec, max_per_pid, max_total)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    mode = "a" if args.follow else "w"

    with open(output_path, mode, encoding="utf-8") as writer:
        audit_thread = None
        if args.follow:
            audit_thread = threading.Thread(
                target=follow_audit_log,
                args=(
                    audit_log,
                    cfg,
                    state,
                    state_lock,
                    pending,
                    pending_lock,
                    writer,
                    write_lock,
                    run_index,
                    link_cmd,
                    args.poll_interval,
                    audit_cursor.offset if audit_cursor else None,
                    audit_cursor.inode if audit_cursor else None,
                ),
                daemon=True,
            )
            audit_thread.start()

        for line in iter_file(ebpf_log, args.follow, args.poll_interval):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("event_type")
            if include_types and event_type not in include_types:
                continue
            pid = event.get("pid")
            if pid is None:
                continue
            ts_dt = parse_ebpf_ts(event.get("ts"))
            if ts_dt is None:
                continue
            comm = event.get("comm") or ""
            if comm in exclude_comm:
                continue
            if event_type == "unix_connect":
                unix = event.get("unix") or {}
                if unix.get("path") in exclude_unix_paths:
                    continue
            if event_type in ("net_connect", "net_send"):
                net = event.get("net") or {}
                dst_ip = net.get("dst_ip")
                dst_port = net.get("dst_port")
                if dst_ip in exclude_net_ips:
                    continue
                if dst_port in exclude_net_ports:
                    continue

            session_id = None
            job_id = None
            with state_lock:
                run_index.maybe_refresh()
                ns_pid = state.ns_pid(pid)
                ns_ppid = state.ns_pid(event.get("ppid"))
                ns_sid = state.ns_sid(pid)
                event["_ns_pid"] = ns_pid
                event["_ns_ppid"] = ns_ppid
                event["_ns_sid"] = ns_sid
                owned = state.is_owned(ns_pid, now=ts_dt, root_pids=run_index.root_pids)
                cmd = state.last_exec_by_pid.get(ns_pid) if link_cmd and owned else None
                if not owned and pending:
                    with pending_lock:
                        if not state.is_owned(ns_pid, now=ts_dt, root_pids=run_index.root_pids):
                            pending.add(ns_pid, ts_dt, event)
                            owned = False
                        else:
                            owned = True
                            if link_cmd:
                                cmd = state.last_exec_by_pid.get(ns_pid)
                if owned:
                    session_id, job_id = state.assign_run(ns_pid, ns_ppid, ns_sid, run_index)

            if not owned:
                continue

            output = build_output(
                event,
                session_id or "unknown",
                job_id,
                cmd,
                cfg.get("schema_version", "ebpf.filtered.v1"),
            )
            write_output(writer, output, write_lock)

    return 0


if __name__ == "__main__":
    sys.exit(main())
