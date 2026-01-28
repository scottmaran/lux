#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import re
import shlex
import sys
import time

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


def load_sessions(sessions_dir: str) -> list[dict]:
    sessions = []
    if not sessions_dir or not os.path.isdir(sessions_dir):
        return sessions
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
        started_at = parse_iso(meta.get("started_at"))
        if started_at is None:
            continue
        ended_at = parse_iso(meta.get("ended_at"))
        session_id = meta.get("session_id") or entry.name
        sessions.append({"id": session_id, "start": started_at, "end": ended_at})
    sessions.sort(key=lambda item: item["start"])
    return sessions


def load_jobs(jobs_dir: str) -> list[dict]:
    jobs = []
    if not jobs_dir or not os.path.isdir(jobs_dir):
        return jobs
    for entry in os.scandir(jobs_dir):
        if not entry.is_dir():
            continue
        input_path = os.path.join(entry.path, "input.json")
        if not os.path.isfile(input_path):
            continue
        try:
            with open(input_path, "r", encoding="utf-8") as handle:
                meta = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        job_id = meta.get("job_id") or entry.name
        start = parse_iso(meta.get("started_at") or meta.get("submitted_at"))
        status_path = os.path.join(entry.path, "status.json")
        status = {}
        if os.path.isfile(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as handle:
                    status = json.load(handle)
            except (OSError, json.JSONDecodeError):
                status = {}
        if status.get("started_at"):
            start = parse_iso(status.get("started_at")) or start
        end = parse_iso(status.get("ended_at"))
        if start is None:
            continue
        jobs.append({"id": job_id, "start": start, "end": end})
    jobs.sort(key=lambda item: item["start"])
    return jobs


class TimeWindowIndex:
    def __init__(self, sessions_dir: str, jobs_dir: str, refresh_sec: float = 1.0):
        self.sessions_dir = sessions_dir
        self.jobs_dir = jobs_dir
        self.refresh_sec = refresh_sec
        self.sessions = []
        self.jobs = []
        self.last_refresh = 0.0

    def maybe_refresh(self) -> None:
        now = time.time()
        if now - self.last_refresh < self.refresh_sec:
            return
        self.sessions = load_sessions(self.sessions_dir)
        self.jobs = load_jobs(self.jobs_dir)
        self.last_refresh = now

    def force_refresh(self) -> None:
        self.sessions = load_sessions(self.sessions_dir)
        self.jobs = load_jobs(self.jobs_dir)
        self.last_refresh = time.time()

    def _match(self, items: list[dict], ts: dt.datetime) -> str | None:
        for item in reversed(items):
            if ts < item["start"]:
                continue
            end = item["end"]
            if end is None or ts <= end:
                return item["id"]
        return None

    def lookup(self, ts: dt.datetime) -> tuple[str, str | None]:
        self.maybe_refresh()
        session_id = self._match(self.sessions, ts)
        if session_id:
            return session_id, None
        job_id = self._match(self.jobs, ts)
        if job_id:
            return "unknown", job_id
        return "unknown", None


class OwnershipState:
    def __init__(self, ttl_sec: int | float = 0) -> None:
        self.owned_pids: dict[int, dt.datetime] = {}
        self.last_exec_by_pid: dict[int, str] = {}
        self.ttl_sec = ttl_sec

    def _prune(self, now: dt.datetime) -> None:
        if not self.ttl_sec:
            return
        cutoff = now - dt.timedelta(seconds=self.ttl_sec)
        stale = [pid for pid, ts in self.owned_pids.items() if ts < cutoff]
        for pid in stale:
            self.owned_pids.pop(pid, None)
            self.last_exec_by_pid.pop(pid, None)

    def is_owned(self, pid: int | None, now: dt.datetime | None = None) -> bool:
        if pid is None:
            return False
        if now:
            self._prune(now)
        return pid in self.owned_pids

    def mark_owned(
        self,
        pid: int | None,
        ppid: int | None,
        uid: int | None,
        comm: str,
        agent_uid: int | None,
        root_comm: set[str],
        ts: dt.datetime,
        cmd: str | None = None,
    ) -> bool:
        if pid is None:
            return False
        self._prune(ts)
        if ppid is not None and ppid in self.owned_pids:
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


def build_ownership(audit_log: str, cfg: dict) -> OwnershipState:
    state = OwnershipState(cfg.get("ownership", {}).get("pid_ttl_sec", 0))
    exec_cfg = cfg.get("exec", {})
    shell_comm = set(exec_cfg.get("shell_comm", ["bash", "sh"]))
    shell_flag = exec_cfg.get("shell_cmd_flag", "-lc")
    exec_keys = set(cfg.get("ownership", {}).get("exec_keys", ["exec"]))
    agent_uid = cfg.get("ownership", {}).get("uid")
    root_comm = set(cfg.get("ownership", {}).get("root_comm", []))

    current_seq = None
    current_records: list[dict] = []

    def flush(records: list[dict]) -> None:
        syscall = next((r for r in records if r["type"] == "SYSCALL"), None)
        if not syscall:
            return
        audit_key = sanitize_key(syscall["fields"].get("key"))
        if audit_key not in exec_keys:
            return
        pid = parse_int(syscall["fields"].get("pid"))
        ppid = parse_int(syscall["fields"].get("ppid"))
        uid = parse_int(syscall["fields"].get("uid"))
        comm = syscall["fields"].get("comm") or ""
        ts = syscall["ts"]
        if ts is None:
            return
        exec_records = [r for r in records if r["type"] == "EXECVE"]
        argv = parse_execve_args(exec_records)
        cmd = derive_cmd(argv, comm, shell_comm, shell_flag)
        state.mark_owned(pid, ppid, uid, comm, agent_uid, root_comm, ts, cmd=cmd)

    try:
        handle = open(audit_log, "r", encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return state

    with handle:
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
    return state


def iter_file(path: str, follow: bool, poll_interval: float):
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
        position = 0

    while True:
        try:
            reopen()
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
        time.sleep(poll_interval)
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            continue
        if inode is None or stat.st_ino != inode:
            reopen()
            continue
        if stat.st_size < position:
            reopen()


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

    state = build_ownership(audit_log, cfg)
    windows = TimeWindowIndex(sessions_dir, jobs_dir)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    mode = "a" if args.follow else "w"

    with open(output_path, mode, encoding="utf-8") as writer:
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
            ts_dt = parse_ebpf_ts(event.get("ts"))
            if ts_dt is None:
                continue
            if not state.is_owned(pid, now=ts_dt):
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

            session_id, job_id = windows.lookup(ts_dt)

            output = {
                "schema_version": cfg.get("schema_version", "ebpf.filtered.v1"),
                "session_id": session_id,
                "ts": event.get("ts"),
                "source": "ebpf",
                "event_type": event_type,
                "pid": event.get("pid"),
                "ppid": event.get("ppid"),
                "uid": event.get("uid"),
                "gid": event.get("gid"),
                "comm": comm,
                "cgroup_id": event.get("cgroup_id"),
                "syscall_result": event.get("syscall_result"),
                "agent_owned": True,
            }
            if job_id:
                output["job_id"] = job_id
            if link_cmd and pid in state.last_exec_by_pid:
                output["cmd"] = state.last_exec_by_pid[pid]
            if event_type in ("net_connect", "net_send") and event.get("net") is not None:
                output["net"] = event.get("net")
            if event_type in ("dns_query", "dns_response") and event.get("dns") is not None:
                output["dns"] = event.get("dns")
            if event_type == "unix_connect" and event.get("unix") is not None:
                output["unix"] = event.get("unix")

            writer.write(json.dumps(output, separators=(",", ":")) + "\n")
            writer.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
