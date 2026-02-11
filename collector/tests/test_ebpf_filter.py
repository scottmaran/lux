import json
import os
import subprocess
import sys
import tempfile
import unittest
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


FILTER_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "filter_ebpf_logs.py"


def make_syscall(ts: str, seq: int, pid: int, ppid: int, uid: int, gid: int, comm: str, exe: str, key: str) -> str:
    return (
        f'type=SYSCALL msg=audit({ts}:{seq}): arch=c00000b7 syscall=221 success=yes exit=0 '
        f'pid={pid} ppid={ppid} uid={uid} gid={gid} comm="{comm}" exe="{exe}" key="{key}"'
    )


def make_execve(ts: str, seq: int, argv: list[str]) -> str:
    args = " ".join(f'a{i}="{arg}"' for i, arg in enumerate(argv))
    return f"type=EXECVE msg=audit({ts}:{seq}): argc={len(argv)} {args}"


def make_net_event(ts: str, pid: int, ppid: int, comm: str, dst_ip: str, dst_port: int) -> dict:
    return {
        "schema_version": "ebpf.v1",
        "ts": ts,
        "event_type": "net_connect",
        "pid": pid,
        "ppid": ppid,
        "uid": 1001,
        "gid": 1001,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "net": {
            "protocol": "tcp",
            "family": "ipv4",
            "src_ip": "172.18.0.3",
            "src_port": 44444,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
        },
    }


def make_dns_event(ts: str, pid: int, ppid: int, comm: str, event_type: str) -> dict:
    payload = {
        "transport": "udp",
        "query_name": "example.com",
        "query_type": "A",
    }
    if event_type == "dns_query":
        payload.update({"server_ip": "127.0.0.11", "server_port": 53})
    else:
        payload.update({"rcode": "NOERROR", "answers": ["93.184.216.34"]})
    return {
        "schema_version": "ebpf.v1",
        "ts": ts,
        "event_type": event_type,
        "pid": pid,
        "ppid": ppid,
        "uid": 1001,
        "gid": 1001,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "dns": payload,
    }


def make_unix_event(ts: str, pid: int, ppid: int, comm: str, path: str) -> dict:
    return {
        "schema_version": "ebpf.v1",
        "ts": ts,
        "event_type": "unix_connect",
        "pid": pid,
        "ppid": ppid,
        "uid": 1001,
        "gid": 1001,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "unix": {"path": path, "abstract": False, "sock_type": "stream"},
    }


class EbpfFilterTests(unittest.TestCase):
    def run_filter(
        self,
        audit_lines: list[str],
        ebpf_events: list[dict],
        config: dict,
        sessions: list[dict] | None = None,
        jobs: list[dict] | None = None,
    ) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log = os.path.join(tmpdir, "audit.log")
            ebpf_log = os.path.join(tmpdir, "ebpf.jsonl")
            output_log = os.path.join(tmpdir, "filtered_ebpf.jsonl")
            sessions_dir = os.path.join(tmpdir, "sessions")
            jobs_dir = os.path.join(tmpdir, "jobs")
            os.makedirs(sessions_dir, exist_ok=True)
            os.makedirs(jobs_dir, exist_ok=True)

            Path(audit_log).write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
            Path(ebpf_log).write_text(
                "\n".join(json.dumps(ev) for ev in ebpf_events) + "\n",
                encoding="utf-8",
            )

            if sessions:
                for meta in sessions:
                    session_path = Path(sessions_dir) / meta["session_id"]
                    session_path.mkdir(parents=True, exist_ok=True)
                    (session_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

            if jobs:
                for meta in jobs:
                    job_path = Path(jobs_dir) / meta["job_id"]
                    job_path.mkdir(parents=True, exist_ok=True)
                    (job_path / "input.json").write_text(json.dumps(meta), encoding="utf-8")
                    status = meta.get("status")
                    if status:
                        (job_path / "status.json").write_text(json.dumps(status), encoding="utf-8")

            cfg = dict(config)
            cfg["input"] = {"audit_log": audit_log, "ebpf_log": ebpf_log}
            cfg["output"] = {"jsonl": output_log}
            cfg["sessions_dir"] = sessions_dir
            cfg["jobs_dir"] = jobs_dir

            config_path = os.path.join(tmpdir, "config.json")
            Path(config_path).write_text(json.dumps(cfg), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(FILTER_SCRIPT), "--config", config_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr.strip())

            if not os.path.exists(output_log):
                return []
            lines = Path(output_log).read_text(encoding="utf-8").splitlines()
            return [json.loads(line) for line in lines if line.strip()]

    def base_config(self) -> dict:
        return {
            "schema_version": "ebpf.filtered.v1",
            "ownership": {"uid": 1001, "root_comm": ["codex"], "pid_ttl_sec": 0},
            "include": {
                "event_types": [
                    "net_connect",
                    "net_send",
                    "dns_query",
                    "dns_response",
                    "unix_connect",
                ]
            },
            "exclude": {"comm": [], "unix_paths": [], "net_dst_ports": [], "net_dst_ips": []},
            "linking": {"attach_cmd_to_net": True, "attach_cmd_strategy": "last_exec_same_pid"},
        }

    def start_follow_filter(self, config: dict, audit_lines: list[str] | None = None) -> tuple:
        tmpdir = tempfile.TemporaryDirectory()
        audit_log = os.path.join(tmpdir.name, "audit.log")
        ebpf_log = os.path.join(tmpdir.name, "ebpf.jsonl")
        output_log = os.path.join(tmpdir.name, "filtered_ebpf.jsonl")
        sessions_dir = os.path.join(tmpdir.name, "sessions")
        jobs_dir = os.path.join(tmpdir.name, "jobs")
        os.makedirs(sessions_dir, exist_ok=True)
        os.makedirs(jobs_dir, exist_ok=True)

        Path(audit_log).write_text("\n".join(audit_lines or []) + ("\n" if audit_lines else ""), encoding="utf-8")
        Path(ebpf_log).write_text("", encoding="utf-8")

        cfg = dict(config)
        cfg["input"] = {"audit_log": audit_log, "ebpf_log": ebpf_log}
        cfg["output"] = {"jsonl": output_log}
        cfg["sessions_dir"] = sessions_dir
        cfg["jobs_dir"] = jobs_dir

        config_path = os.path.join(tmpdir.name, "config.json")
        Path(config_path).write_text(json.dumps(cfg), encoding="utf-8")

        proc = subprocess.Popen(
            [sys.executable, str(FILTER_SCRIPT), "--config", config_path, "--follow", "--poll-interval", "0.05"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return tmpdir, proc, audit_log, ebpf_log, output_log

    def append_audit(self, path: str, lines: list[str]) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
            handle.flush()

    def append_ebpf(self, path: str, events: list[dict]) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")
            handle.flush()

    def wait_for_events(self, path: str, min_count: int, timeout: float = 3.0) -> list[dict]:
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(path):
                lines = Path(path).read_text(encoding="utf-8").splitlines()
                events = [json.loads(line) for line in lines if line.strip()]
                if len(events) >= min_count:
                    return events
            time.sleep(0.05)
        raise AssertionError(f"Timed out waiting for {min_count} events in {path}")

    def stop_follow_filter(self, tmpdir, proc) -> None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        tmpdir.cleanup()

    def test_owned_pid_includes_event_and_cmd(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.123"
        ebpf_ts = "2026-01-22T00:00:00.123456789Z"
        session_id = "session_test_0001"

        audit_lines = [
            make_syscall(ts_sec, 1, 100, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
            make_syscall(ts_sec, 2, 101, 100, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts_sec, 2, ["bash", "-lc", "curl example.com"]),
        ]

        ebpf_events = [make_net_event(ebpf_ts, 101, 100, "bash", "93.184.216.34", 443)]

        sessions = [
            {
                "session_id": session_id,
                "started_at": base.isoformat(),
                "ended_at": (base + timedelta(seconds=5)).isoformat(),
                "mode": "tui",
                "root_pid": 100,
            }
        ]

        events = self.run_filter(audit_lines, ebpf_events, self.base_config(), sessions=sessions)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["session_id"], session_id)
        self.assertEqual(events[0]["event_type"], "net_connect")
        self.assertIn("cmd", events[0])
        self.assertEqual(events[0]["cmd"], "curl example.com")

    def test_exclude_comm(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 1, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.456"
        ebpf_ts = "2026-01-22T00:00:01.456000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 200, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
            make_syscall(ts_sec, 2, 201, 200, 1001, 1001, "dockerd", "/usr/bin/dockerd", "exec"),
            make_execve(ts_sec, 2, ["dockerd"]),
        ]

        ebpf_events = [make_net_event(ebpf_ts, 201, 200, "dockerd", "93.184.216.34", 443)]
        config = self.base_config()
        config["exclude"]["comm"] = ["dockerd"]

        events = self.run_filter(audit_lines, ebpf_events, config)
        self.assertEqual(len(events), 0)

    def test_exclude_unix_path(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 2, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.789"
        ebpf_ts = "2026-01-22T00:00:02.789000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 300, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
            make_syscall(ts_sec, 2, 301, 300, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts_sec, 2, ["bash", "-lc", "true"]),
        ]

        ebpf_events = [make_unix_event(ebpf_ts, 301, 300, "bash", "/var/run/nscd/socket")]
        config = self.base_config()
        config["exclude"]["unix_paths"] = ["/var/run/nscd/socket"]

        events = self.run_filter(audit_lines, ebpf_events, config)
        self.assertEqual(len(events), 0)

    def test_dns_query_response_kept(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 3, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.000"
        query_ts = "2026-01-22T00:00:03.000000000Z"
        resp_ts = "2026-01-22T00:00:03.100000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 400, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
            make_syscall(ts_sec, 2, 401, 400, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts_sec, 2, ["bash", "-lc", "true"]),
        ]

        ebpf_events = [
            make_dns_event(query_ts, 401, 400, "bash", "dns_query"),
            make_dns_event(resp_ts, 401, 400, "bash", "dns_response"),
        ]

        events = self.run_filter(audit_lines, ebpf_events, self.base_config())
        event_types = {event["event_type"] for event in events}
        self.assertEqual(event_types, {"dns_query", "dns_response"})

    def test_session_job_precedence(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 4, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.500"
        ebpf_ts = "2026-01-22T00:00:04.500000000Z"
        session_id = "session_test_0002"
        job_id = "job_test_0001"

        audit_lines = [
            make_syscall(ts_sec, 1, 500, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
        ]

        ebpf_events = [make_net_event(ebpf_ts, 500, 1, "codex", "93.184.216.34", 443)]

        sessions = [
            {
                "session_id": session_id,
                "started_at": base.isoformat(),
                "ended_at": (base + timedelta(seconds=5)).isoformat(),
                "mode": "tui",
                "root_pid": 500,
            }
        ]
        jobs = [
            {
                "job_id": job_id,
                "submitted_at": base.isoformat(),
                "started_at": base.isoformat(),
                "root_pid": 600,
                "status": {
                    "job_id": job_id,
                    "started_at": base.isoformat(),
                    "ended_at": (base + timedelta(seconds=5)).isoformat(),
                    "root_pid": 600,
                },
            }
        ]

        events = self.run_filter(audit_lines, ebpf_events, self.base_config(), sessions=sessions, jobs=jobs)
        self.assertEqual(events[0]["session_id"], session_id)
        self.assertNotIn("job_id", events[0])

    def test_event_type_filter(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 5, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.600"
        ebpf_ts = "2026-01-22T00:00:05.600000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 600, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
        ]

        ebpf_events = [
            {
                "schema_version": "ebpf.v1",
                "ts": ebpf_ts,
                "event_type": "net_recv",
                "pid": 600,
                "ppid": 1,
                "uid": 1001,
                "gid": 1001,
                "comm": "codex",
                "cgroup_id": "0x0000000000000001",
                "syscall_result": 0,
                "net": {"protocol": "tcp", "family": "ipv4"},
            }
        ]

        events = self.run_filter(audit_lines, ebpf_events, self.base_config())
        self.assertEqual(len(events), 0)

    def test_net_destination_exclusion(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 6, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.700"
        ebpf_ts = "2026-01-22T00:00:06.700000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 700, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
        ]

        ebpf_events = [make_net_event(ebpf_ts, 700, 1, "codex", "203.0.113.10", 443)]
        config = self.base_config()
        config["exclude"]["net_dst_ips"] = ["203.0.113.10"]

        events = self.run_filter(audit_lines, ebpf_events, config)
        self.assertEqual(len(events), 0)

    def test_follow_updates_ownership_from_audit_tail(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 7, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.800"
        ebpf_ts = "2026-01-22T00:00:07.800000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 800, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
            make_syscall(ts_sec, 2, 801, 800, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts_sec, 2, ["bash", "-lc", "curl example.com"]),
        ]

        config = self.base_config()
        tmpdir, proc, audit_log, ebpf_log, output_log = self.start_follow_filter(config)
        try:
            time.sleep(0.1)
            self.append_audit(audit_log, audit_lines)
            time.sleep(0.35)
            self.append_ebpf(ebpf_log, [make_net_event(ebpf_ts, 801, 800, "bash", "93.184.216.34", 443)])
            events = self.wait_for_events(output_log, 1)
            self.assertEqual(events[0]["event_type"], "net_connect")
            self.assertEqual(events[0]["cmd"], "curl example.com")
        finally:
            self.stop_follow_filter(tmpdir, proc)

    def test_follow_pending_buffers_out_of_order(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 8, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.900"
        ebpf_ts = "2026-01-22T00:00:08.900000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 900, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
            make_syscall(ts_sec, 2, 901, 900, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts_sec, 2, ["bash", "-lc", "curl example.com"]),
        ]

        config = self.base_config()
        config["pending_buffer"] = {"enabled": True, "ttl_sec": 2.0, "max_per_pid": 100, "max_total": 1000}
        tmpdir, proc, audit_log, ebpf_log, output_log = self.start_follow_filter(config)
        try:
            time.sleep(0.1)
            self.append_ebpf(ebpf_log, [make_net_event(ebpf_ts, 901, 900, "bash", "93.184.216.34", 443)])
            time.sleep(0.1)
            self.append_audit(audit_log, audit_lines)
            events = self.wait_for_events(output_log, 1)
            self.assertEqual(events[0]["event_type"], "net_connect")
        finally:
            self.stop_follow_filter(tmpdir, proc)

    def test_follow_audit_rotation_does_not_skip_new_execs(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 9, tzinfo=timezone.utc)
        ts_sec = f"{int(base.timestamp())}.950"
        ebpf_ts = "2026-01-22T00:00:09.950000000Z"

        audit_lines = [
            make_syscall(ts_sec, 1, 950, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts_sec, 1, ["codex"]),
        ]

        config = self.base_config()
        config["pending_buffer"] = {"enabled": True, "ttl_sec": 2.0, "max_per_pid": 100, "max_total": 1000}
        tmpdir, proc, audit_log, ebpf_log, output_log = self.start_follow_filter(config)
        try:
            time.sleep(0.1)
            rotated = audit_log + ".1"
            os.replace(audit_log, rotated)
            Path(audit_log).write_text("", encoding="utf-8")
            time.sleep(0.1)
            self.append_audit(audit_log, audit_lines)
            time.sleep(0.1)
            self.append_ebpf(ebpf_log, [make_net_event(ebpf_ts, 950, 1, "codex", "93.184.216.34", 443)])
            events = self.wait_for_events(output_log, 1)
            self.assertEqual(events[0]["pid"], 950)
        finally:
            self.stop_follow_filter(tmpdir, proc)


if __name__ == "__main__":
    unittest.main()
