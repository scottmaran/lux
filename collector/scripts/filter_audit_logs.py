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
    parser = argparse.ArgumentParser(description="Filter auditd logs into JSONL.")
    parser.add_argument(
        "--config",
        default=os.getenv("COLLECTOR_FILTER_CONFIG", "/etc/collector/filtering.yaml"),
        help="Path to filtering.yaml",
    )
    parser.add_argument("--follow", action="store_true", help="Tail the audit log")
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
            "collector-audit-filter: missing PyYAML and config is not valid JSON"
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


def argv_prefix_match(argv: list[str], prefixes: list[list[str]]) -> bool:
    for prefix in prefixes:
        if len(argv) < len(prefix):
            continue
        if argv[: len(prefix)] == prefix:
            return True
    return False


def select_path(path_records: list[dict], preferred: str | None) -> str | None:
    if preferred:
        for record in path_records:
            if record.get("nametype") == preferred:
                return record.get("name")
    for record in path_records:
        nametype = record.get("nametype")
        if nametype == "PARENT":
            continue
        name = record.get("name")
        if name and name != "(null)":
            return name
    return None


def derive_fs_event_type(audit_key: str | None, nametypes: set[str]) -> str:
    if "CREATE" in nametypes and "DELETE" in nametypes:
        return "fs_rename"
    if "CREATE" in nametypes:
        return "fs_create"
    if "DELETE" in nametypes:
        return "fs_unlink"
    if audit_key == "fs_meta":
        return "fs_meta"
    return "fs_write"


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


class FilterState:
    def __init__(self) -> None:
        self.owned_pids = set()
        self.last_exec_by_pid = {}

    def is_owned(self, pid: int | None) -> bool:
        return pid is not None and pid in self.owned_pids

    def mark_owned(
        self,
        pid: int | None,
        ppid: int | None,
        uid: int | None,
        agent_uid: int | None,
        comm: str,
        root_comm: set[str],
    ) -> bool:
        if pid is None:
            return False
        if ppid is not None and ppid in self.owned_pids:
            self.owned_pids.add(pid)
            return True
        if agent_uid is None or uid is None or uid != agent_uid:
            return False
        if root_comm and comm not in root_comm:
            return False
        self.owned_pids.add(pid)
        return True


def build_event(records: list[dict], cfg: dict, state: FilterState) -> tuple[dict, dt.datetime] | None:
    syscall = next((r for r in records if r["type"] == "SYSCALL"), None)
    if not syscall:
        return None
    fields = syscall["fields"]
    audit_key = sanitize_key(fields.get("key"))
    exec_cfg = cfg.get("exec", {})
    fs_cfg = cfg.get("fs", {})
    include_exec = set(exec_cfg.get("include_keys", []))
    include_fs = set(fs_cfg.get("include_keys", []))
    if audit_key not in include_exec and audit_key not in include_fs:
        return None

    pid = parse_int(fields.get("pid"))
    ppid = parse_int(fields.get("ppid"))
    uid = parse_int(fields.get("uid"))
    gid = parse_int(fields.get("gid"))
    comm = fields.get("comm") or ""
    exe = fields.get("exe") or ""
    cwd_record = next((r for r in records if r["type"] == "CWD"), None)
    cwd = cwd_record["fields"].get("cwd") if cwd_record else None
    seq = syscall["seq"]
    ts = syscall["ts"]
    ts_iso = syscall["ts_iso"]
    if ts is None:
        return None

    agent_uid = cfg.get("agent_ownership", {}).get("uid")
    root_comm = set(cfg.get("agent_ownership", {}).get("root_comm", []))
    shell_comm = set(exec_cfg.get("shell_comm", []))

    if audit_key in include_exec:
        exec_records = [r for r in records if r["type"] == "EXECVE"]
        argv = parse_execve_args(exec_records)
        cmd = derive_cmd(argv, comm, shell_comm, exec_cfg.get("shell_cmd_flag", "-lc"))

        owned = state.mark_owned(pid, ppid, uid, agent_uid, comm, root_comm)
        excluded = comm in set(exec_cfg.get("helper_exclude_comm", []))
        if argv_prefix_match(argv, exec_cfg.get("helper_exclude_argv_prefix", [])):
            excluded = True
        if not owned or excluded:
            return None

        event = {
            "schema_version": cfg.get("schema_version", "auditd.filtered.v1"),
            "session_id": "unknown",
            "ts": ts_iso,
            "source": "audit",
            "event_type": "exec",
            "cmd": cmd,
            "cwd": cwd,
            "comm": comm,
            "exe": exe,
            "pid": pid,
            "ppid": ppid,
            "uid": uid,
            "gid": gid,
            "audit_seq": seq,
            "audit_key": audit_key,
            "agent_owned": True,
        }

        if cfg.get("linking", {}).get("attach_cmd_to_fs", False) and pid is not None:
            state.last_exec_by_pid[pid] = cmd

        return event, ts

    if audit_key in include_fs:
        if not state.is_owned(pid):
            return None
        path_records = []
        for record in records:
            if record["type"] != "PATH":
                continue
            path_records.append(
                {
                    "name": record["fields"].get("name"),
                    "nametype": record["fields"].get("nametype"),
                }
            )
        nametypes = {record.get("nametype") for record in path_records if record.get("nametype")}
        event_type = derive_fs_event_type(audit_key, nametypes)
        preferred = None
        if event_type in ("fs_create", "fs_rename"):
            preferred = "CREATE"
        elif event_type == "fs_unlink":
            preferred = "DELETE"
        path = select_path(path_records, preferred)
        if not path:
            return None
        prefixes = fs_cfg.get("include_paths_prefix", [])
        if prefixes and not any(path.startswith(prefix) for prefix in prefixes):
            return None

        event = {
            "schema_version": cfg.get("schema_version", "auditd.filtered.v1"),
            "session_id": "unknown",
            "ts": ts_iso,
            "source": "audit",
            "event_type": event_type,
            "path": path,
            "cwd": cwd,
            "comm": comm,
            "exe": exe,
            "pid": pid,
            "ppid": ppid,
            "uid": uid,
            "gid": gid,
            "audit_seq": seq,
            "audit_key": audit_key,
            "agent_owned": True,
        }

        if cfg.get("linking", {}).get("attach_cmd_to_fs", False) and pid is not None:
            cmd = state.last_exec_by_pid.get(pid)
            if cmd:
                event["cmd"] = cmd

        return event, ts

    return None


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
    grouping = cfg.get("grouping", {}).get("strategy")
    if grouping and grouping != "audit_seq":
        print(f"collector-audit-filter: unsupported grouping strategy '{grouping}'", file=sys.stderr)
        return 2

    audit_log = os.getenv("COLLECTOR_AUDIT_LOG") or cfg.get("input", {}).get("audit_log", "/logs/audit.log")
    output_path = os.getenv("COLLECTOR_FILTER_OUTPUT") or cfg.get("output", {}).get(
        "jsonl", "/logs/filtered_audit.jsonl"
    )
    sessions_dir = os.getenv("COLLECTOR_SESSIONS_DIR") or cfg.get("sessions_dir", "/logs/sessions")
    jobs_dir = os.getenv("COLLECTOR_JOBS_DIR") or cfg.get("jobs_dir", "/logs/jobs")

    state = FilterState()
    windows = TimeWindowIndex(sessions_dir, jobs_dir)
    pending = []
    pending_delay_sec = 2.0

    def emit(event: dict, ts_dt: dt.datetime) -> None:
        session_id, job_id = windows.lookup(ts_dt)
        if session_id == "unknown" and not job_id and args.follow:
            windows.force_refresh()
            session_id, job_id = windows.lookup(ts_dt)
        event["session_id"] = session_id
        if job_id:
            event["job_id"] = job_id
        writer.write(json.dumps(event, separators=(",", ":")) + "\n")
        writer.flush()

    def flush_pending() -> None:
        if not pending:
            return
        now = time.monotonic()
        remaining = []
        for event, ts_dt, enqueued in pending:
            session_id, job_id = windows.lookup(ts_dt)
            if session_id != "unknown" or job_id:
                event["session_id"] = session_id
                if job_id:
                    event["job_id"] = job_id
                writer.write(json.dumps(event, separators=(",", ":")) + "\n")
                writer.flush()
                continue
            if now - enqueued >= pending_delay_sec:
                event["session_id"] = "unknown"
                writer.write(json.dumps(event, separators=(",", ":")) + "\n")
                writer.flush()
                continue
            remaining.append((event, ts_dt, enqueued))
        pending[:] = remaining

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    mode = "a" if args.follow else "w"
    with open(output_path, mode, encoding="utf-8") as writer:
        current_seq = None
        current_records = []
        for line in iter_file(audit_log, args.follow, args.poll_interval):
            record = parse_line(line)
            if not record:
                continue
            seq = record["seq"]
            if current_seq is None:
                current_seq = seq
            if seq != current_seq:
                result = build_event(current_records, cfg, state)
                if result:
                    event, ts_dt = result
                    if args.follow:
                        pending.append((event, ts_dt, time.monotonic()))
                    else:
                        emit(event, ts_dt)
                flush_pending()
                current_records = [record]
                current_seq = seq
            else:
                current_records.append(record)
        if current_records:
            result = build_event(current_records, cfg, state)
            if result:
                event, ts_dt = result
                if args.follow:
                    pending.append((event, ts_dt, time.monotonic()))
                else:
                    emit(event, ts_dt)
            flush_pending()
    return 0


if __name__ == "__main__":
    sys.exit(main())
