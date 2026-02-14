#!/usr/bin/env python3
import argparse
import datetime as dt
import errno
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


def env_root_comm_override() -> set[str] | None:
    raw = os.getenv("COLLECTOR_ROOT_COMM")
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    values = {item.strip() for item in stripped.split(",") if item.strip()}
    return values or None


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


def parse_success(value: str | None, exit_code: int | None) -> bool | None:
    if value == "yes":
        return True
    if value == "no":
        return False
    if exit_code is None:
        return None
    return exit_code >= 0


def errno_name(exit_code: int | None) -> str | None:
    if exit_code is None or exit_code >= 0:
        return None
    return errno.errorcode.get(-exit_code)


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
        root_pid = parse_int(meta.get("root_pid"))
        session_id = meta.get("session_id") or entry.name
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


class FilterState:
    def __init__(self) -> None:
        self.owned_pids = set()
        self.last_exec_by_pid = {}
        self.pid_to_session = {}
        self.pid_to_job = {}
        self.ns_pid_cache = {}
        self.ns_sid_cache = {}

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

    def is_owned(self, pid: int | None, root_pids: set[int] | None = None) -> bool:
        if pid is None:
            return False
        if pid in self.owned_pids:
            return True
        if root_pids and pid in root_pids:
            self.owned_pids.add(pid)
            return True
        return False

    def mark_owned(
        self,
        pid: int | None,
        ppid: int | None,
        uid: int | None,
        agent_uid: int | None,
        comm: str,
        root_comm: set[str],
        root_pids: set[int] | None = None,
    ) -> bool:
        if pid is None:
            return False
        if root_pids and pid in root_pids:
            self.owned_pids.add(pid)
            return True
        if ppid is not None and (ppid in self.owned_pids or (root_pids and ppid in root_pids)):
            self.owned_pids.add(pid)
            return True
        if agent_uid is None or uid is None or uid != agent_uid:
            return False
        if root_comm and comm not in root_comm:
            return False
        self.owned_pids.add(pid)
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


def build_event(
    records: list[dict],
    cfg: dict,
    state: FilterState,
    run_index: RunIndex,
) -> tuple[dict, dt.datetime] | None:
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
    ns_pid = state.ns_pid(pid)
    ns_ppid = state.ns_pid(ppid)
    ns_sid = state.ns_sid(pid)
    uid = parse_int(fields.get("uid"))
    gid = parse_int(fields.get("gid"))
    comm = fields.get("comm") or ""
    exe = fields.get("exe") or ""
    cwd_record = next((r for r in records if r["type"] == "CWD"), None)
    cwd = cwd_record["fields"].get("cwd") if cwd_record else None
    path_records = [
        {"name": record["fields"].get("name"), "nametype": record["fields"].get("nametype")}
        for record in records
        if record["type"] == "PATH"
    ]
    seq = syscall["seq"]
    ts = syscall["ts"]
    ts_iso = syscall["ts_iso"]
    if ts is None:
        return None

    run_index.maybe_refresh()
    root_pids = run_index.root_pids
    agent_uid = cfg.get("agent_ownership", {}).get("uid")
    root_comm = set(cfg.get("agent_ownership", {}).get("root_comm", []))
    env_root_comm = env_root_comm_override()
    if env_root_comm is not None:
        root_comm = env_root_comm
    shell_comm = set(exec_cfg.get("shell_comm", []))

    if audit_key in include_exec:
        exec_records = [r for r in records if r["type"] == "EXECVE"]
        argv = parse_execve_args(exec_records)
        cmd = derive_cmd(argv, comm, shell_comm, exec_cfg.get("shell_cmd_flag", "-lc"))
        exec_exit = parse_int(fields.get("exit"))
        exec_success = parse_success(fields.get("success"), exec_exit)
        exec_errno = errno_name(exec_exit)
        exec_attempted_path = select_path(path_records, "NORMAL")
        if exec_success is False and exec_attempted_path and (not argv or cmd == comm or not cmd):
            cmd = exec_attempted_path

        owned = state.mark_owned(ns_pid, ns_ppid, uid, agent_uid, comm, root_comm, root_pids)
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
            "_ns_pid": ns_pid,
            "_ns_ppid": ns_ppid,
            "_ns_sid": ns_sid,
        }
        if exec_success is not None:
            event["exec_success"] = exec_success
        if exec_exit is not None:
            event["exec_exit"] = exec_exit
        if exec_errno:
            event["exec_errno_name"] = exec_errno
        if exec_attempted_path:
            event["exec_attempted_path"] = exec_attempted_path

        if cfg.get("linking", {}).get("attach_cmd_to_fs", False) and pid is not None:
            if ns_pid is not None:
                state.last_exec_by_pid[ns_pid] = cmd

        return event, ts

    if audit_key in include_fs:
        owned = state.mark_owned(ns_pid, ns_ppid, uid, agent_uid, comm, root_comm, root_pids)
        if not owned:
            return None
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
            "_ns_pid": ns_pid,
            "_ns_ppid": ns_ppid,
            "_ns_sid": ns_sid,
        }

        if cfg.get("linking", {}).get("attach_cmd_to_fs", False) and ns_pid is not None:
            cmd = state.last_exec_by_pid.get(ns_pid)
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
    run_index = RunIndex(sessions_dir, jobs_dir)
    pending = []
    # In follow mode, session/job root markers can arrive slightly after the first owned
    # audit events. Buffer a bit longer to avoid emitting "unknown" owner rows that pollute
    # the merged timeline and break strict ownership validation.
    pending_delay_sec = 10.0

    def assign_run(event: dict, force_refresh: bool = False) -> tuple[str | None, str | None]:
        pid = event.get("_ns_pid")
        ppid = event.get("_ns_ppid")
        sid = event.get("_ns_sid")
        if pid is None:
            pid = event.get("pid")
            ppid = event.get("ppid")
            sid = state.ns_sid(pid)
        session_id, job_id = state.assign_run(pid, ppid, sid, run_index)
        if not session_id and not job_id and force_refresh:
            run_index.force_refresh()
            session_id, job_id = state.assign_run(pid, ppid, sid, run_index)
        if session_id:
            event["session_id"] = session_id
            event.pop("job_id", None)
        elif job_id:
            event["session_id"] = "unknown"
            event["job_id"] = job_id
        else:
            event["session_id"] = "unknown"
            event.pop("job_id", None)
        return session_id, job_id

    def emit(event: dict) -> None:
        event.pop("_ns_pid", None)
        event.pop("_ns_ppid", None)
        event.pop("_ns_sid", None)
        writer.write(json.dumps(event, separators=(",", ":")) + "\n")
        writer.flush()

    def flush_pending() -> None:
        if not pending:
            return
        now = time.monotonic()
        remaining = []
        run_index.force_refresh()
        for event, enqueued in pending:
            session_id, job_id = assign_run(event)
            if session_id or job_id:
                emit(event)
                continue
            if now - enqueued >= pending_delay_sec:
                # Drop still-unattributed events instead of emitting ownerless rows.
                continue
            remaining.append((event, enqueued))
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
                result = build_event(current_records, cfg, state, run_index)
                if result:
                    event, _ts_dt = result
                    if args.follow:
                        session_id, job_id = assign_run(event, force_refresh=True)
                        if session_id or job_id:
                            emit(event)
                        else:
                            pending.append((event, time.monotonic()))
                    else:
                        assign_run(event)
                        emit(event)
                flush_pending()
                current_records = [record]
                current_seq = seq
            else:
                current_records.append(record)
        if current_records:
            result = build_event(current_records, cfg, state, run_index)
            if result:
                event, _ts_dt = result
                if args.follow:
                    session_id, job_id = assign_run(event, force_refresh=True)
                    if session_id or job_id:
                        emit(event)
                    else:
                        pending.append((event, time.monotonic()))
                else:
                    assign_run(event)
                    emit(event)
            flush_pending()
    return 0


if __name__ == "__main__":
    sys.exit(main())
