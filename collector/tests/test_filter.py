import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


FILTER_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "filter_audit_logs.py"



def make_syscall(
    ts: str,
    seq: int,
    pid: int,
    ppid: int,
    uid: int,
    gid: int,
    comm: str,
    exe: str,
    key: str,
    success: str = "yes",
    exit_code: int = 0,
) -> str:
    return (
        f'type=SYSCALL msg=audit({ts}:{seq}): arch=c00000b7 syscall=221 success={success} exit={exit_code} '
        f'pid={pid} ppid={ppid} uid={uid} gid={gid} comm="{comm}" exe="{exe}" key="{key}"'
    )


def make_execve(ts: str, seq: int, argv: list[str]) -> str:
    args = " ".join(f'a{i}="{arg}"' for i, arg in enumerate(argv))
    return f"type=EXECVE msg=audit({ts}:{seq}): argc={len(argv)} {args}"


def make_cwd(ts: str, seq: int, cwd: str) -> str:
    return f'type=CWD msg=audit({ts}:{seq}): cwd="{cwd}"'


def make_path(ts: str, seq: int, name: str, nametype: str) -> str:
    return f'type=PATH msg=audit({ts}:{seq}): item=0 name="{name}" nametype={nametype}'


class AuditFilterTests(unittest.TestCase):
    def run_filter(self, audit_lines: list[str], config: dict, jobs: list[dict] | None = None,
                   sessions: list[dict] | None = None) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log = os.path.join(tmpdir, "audit.log")
            output_log = os.path.join(tmpdir, "filtered.jsonl")
            sessions_dir = os.path.join(tmpdir, "sessions")
            jobs_dir = os.path.join(tmpdir, "jobs")
            os.makedirs(sessions_dir, exist_ok=True)
            os.makedirs(jobs_dir, exist_ok=True)

            Path(audit_log).write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

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
            cfg["input"] = {"audit_log": audit_log}
            cfg["output"] = {"jsonl": output_log}
            cfg["sessions_dir"] = sessions_dir
            cfg["jobs_dir"] = jobs_dir

            config_path = os.path.join(tmpdir, "config.yaml")
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
            "schema_version": "auditd.filtered.v1",
            "grouping": {"strategy": "audit_seq"},
            "agent_ownership": {"uid": 1001, "root_comm": ["codex"]},
            "exec": {
                "include_keys": ["exec"],
                "shell_comm": ["bash", "sh"],
                "shell_cmd_flag": "-lc",
                "helper_exclude_comm": [],
                "helper_exclude_argv_prefix": [],
            },
            "fs": {
                "include_keys": ["fs_watch", "fs_change", "fs_meta"],
                "include_paths_prefix": ["/work/"],
            },
            "linking": {"attach_cmd_to_fs": True, "attach_cmd_strategy": "last_exec_same_pid"},
        }

    def test_exec_cmd_extraction_and_job_id(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.123"
        job_id = "job_test_0001"
        jobs = [{
            "job_id": job_id,
            "submitted_at": base.isoformat(),
            "started_at": base.isoformat(),
            "root_pid": 100,
            "root_sid": 100,
            "status": {
                "job_id": job_id,
                "started_at": base.isoformat(),
                "ended_at": (base + timedelta(seconds=5)).isoformat(),
                "root_pid": 100,
                "root_sid": 100,
            },
        }]

        audit_lines = [
            make_syscall(ts, 1, 100, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
            make_syscall(ts, 2, 101, 100, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts, 2, ["bash", "-lc", "pwd"]),
            make_cwd(ts, 2, "/work"),
        ]

        events = self.run_filter(audit_lines, self.base_config(), jobs=jobs)
        cmds = {event["cmd"] for event in events}
        self.assertIn("pwd", cmds)
        for event in events:
            self.assertEqual(event.get("job_id"), job_id)

    def test_fs_create_with_cmd_link(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.456"
        audit_lines = [
            make_syscall(ts, 1, 200, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
            make_syscall(ts, 2, 201, 200, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts, 2, ["bash", "-lc", "echo hello > /work/a.txt"]),
            make_cwd(ts, 2, "/work"),
            make_syscall(ts, 3, 201, 200, 1001, 1001, "bash", "/usr/bin/bash", "fs_watch"),
            make_path(ts, 3, "/work/a.txt", "CREATE"),
        ]

        events = self.run_filter(audit_lines, self.base_config())
        fs_events = [event for event in events if event["event_type"] == "fs_create"]
        self.assertEqual(len(fs_events), 1)
        self.assertEqual(fs_events[0]["path"], "/work/a.txt")
        self.assertIn("cmd", fs_events[0])

    def test_fs_create_before_child_exec_is_owned_via_parent(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.457"
        audit_lines = [
            make_syscall(ts, 1, 700, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
            make_syscall(ts, 2, 701, 700, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts, 2, ["bash", "-lc", "cat <<'PY' > /work/race.txt\nhello\nPY"]),
            make_cwd(ts, 2, "/work"),
            make_syscall(ts, 3, 702, 701, 1001, 1001, "bash", "/usr/bin/bash", "fs_watch"),
            make_path(ts, 3, "/work/race.txt", "CREATE"),
            make_syscall(ts, 4, 702, 701, 1001, 1001, "cat", "/usr/bin/cat", "exec"),
            make_execve(ts, 4, ["cat"]),
            make_cwd(ts, 4, "/work"),
        ]

        events = self.run_filter(audit_lines, self.base_config())
        fs_events = [event for event in events if event["event_type"] == "fs_create"]
        self.assertEqual(len(fs_events), 1)
        self.assertEqual(fs_events[0]["path"], "/work/race.txt")
        self.assertEqual(fs_events[0]["pid"], 702)

    def test_helper_suppression(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.789"
        config = self.base_config()
        config["exec"]["helper_exclude_comm"] = ["git"]

        audit_lines = [
            make_syscall(ts, 1, 300, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
            make_syscall(ts, 2, 301, 300, 1001, 1001, "git", "/usr/bin/git", "exec"),
            make_execve(ts, 2, ["git", "rev-parse", "--git-dir"]),
        ]

        events = self.run_filter(audit_lines, config)
        comms = {event["comm"] for event in events}
        self.assertNotIn("git", comms)

    def test_path_prefix_filter(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.321"
        audit_lines = [
            make_syscall(ts, 1, 400, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
            make_syscall(ts, 2, 401, 400, 1001, 1001, "bash", "/usr/bin/bash", "exec"),
            make_execve(ts, 2, ["bash", "-lc", "touch /work/ok.txt"]),
            make_syscall(ts, 3, 401, 400, 1001, 1001, "bash", "/usr/bin/bash", "fs_watch"),
            make_path(ts, 3, "/tmp/tmp.txt", "CREATE"),
            make_syscall(ts, 4, 401, 400, 1001, 1001, "bash", "/usr/bin/bash", "fs_watch"),
            make_path(ts, 4, "/work/ok.txt", "CREATE"),
        ]

        events = self.run_filter(audit_lines, self.base_config())
        paths = [event.get("path") for event in events if event["event_type"].startswith("fs_")]
        self.assertEqual(paths, ["/work/ok.txt"])

    def test_session_mapping_precedence(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.654"
        session_id = "session_test_0001"
        job_id = "job_test_0002"
        sessions = [{
            "session_id": session_id,
            "started_at": base.isoformat(),
            "ended_at": (base + timedelta(seconds=5)).isoformat(),
            "mode": "tui",
            "command": "codex",
            "root_pid": 500,
            "root_sid": 500,
        }]
        jobs = [{
            "job_id": job_id,
            "submitted_at": base.isoformat(),
            "started_at": base.isoformat(),
            "root_pid": 600,
            "root_sid": 600,
            "status": {
                "job_id": job_id,
                "started_at": base.isoformat(),
                "ended_at": (base + timedelta(seconds=5)).isoformat(),
                "root_pid": 600,
                "root_sid": 600,
            },
        }]

        audit_lines = [
            make_syscall(ts, 1, 500, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
        ]

        events = self.run_filter(audit_lines, self.base_config(), jobs=jobs, sessions=sessions)
        self.assertEqual(events[0]["session_id"], session_id)
        self.assertNotIn("job_id", events[0])

    def test_session_mapping_falls_back_to_root_sid_when_root_pid_missing(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.655"
        session_id = "session_test_sid_fallback"
        sessions = [{
            "session_id": session_id,
            "started_at": base.isoformat(),
            "ended_at": (base + timedelta(seconds=5)).isoformat(),
            "mode": "tui",
            "command": "codex",
            "root_pid": 500,
            "root_sid": 910,
        }]
        audit_lines = [
            make_syscall(ts, 1, 910, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
        ]

        events = self.run_filter(audit_lines, self.base_config(), sessions=sessions)
        self.assertEqual(events[0]["session_id"], session_id)
        self.assertNotIn("job_id", events[0])

    def test_session_sid_mapping_takes_precedence_over_job_sid_mapping(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.656"
        session_id = "session_test_sid_precedence"
        job_id = "job_test_sid_precedence"
        shared_sid = 920
        sessions = [{
            "session_id": session_id,
            "started_at": base.isoformat(),
            "ended_at": (base + timedelta(seconds=5)).isoformat(),
            "mode": "tui",
            "command": "codex",
            "root_pid": 501,
            "root_sid": shared_sid,
        }]
        jobs = [{
            "job_id": job_id,
            "submitted_at": base.isoformat(),
            "started_at": base.isoformat(),
            "root_pid": 601,
            "root_sid": shared_sid,
            "status": {
                "job_id": job_id,
                "started_at": base.isoformat(),
                "ended_at": (base + timedelta(seconds=5)).isoformat(),
                "root_pid": 601,
                "root_sid": shared_sid,
            },
        }]
        audit_lines = [
            make_syscall(ts, 1, shared_sid, 1, 1001, 1001, "codex", "/usr/bin/codex", "exec"),
            make_execve(ts, 1, ["codex"]),
        ]

        events = self.run_filter(audit_lines, self.base_config(), jobs=jobs, sessions=sessions)
        self.assertEqual(events[0]["session_id"], session_id)
        self.assertNotIn("job_id", events[0])

    def test_exec_failure_includes_status_and_attempted_path(self) -> None:
        base = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)
        ts = f"{int(base.timestamp())}.777"
        attempted = "/home/agent/.codex/tmp/path/codex-arg0/tmp_git"
        audit_lines = [
            make_syscall(
                ts,
                1,
                600,
                1,
                1001,
                1001,
                "codex",
                "/usr/bin/codex",
                "exec",
                success="no",
                exit_code=-2,
            ),
            make_cwd(ts, 1, "/work"),
            make_path(ts, 1, attempted, "UNKNOWN"),
        ]

        events = self.run_filter(audit_lines, self.base_config())
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.get("exec_success"), False)
        self.assertEqual(event.get("exec_exit"), -2)
        self.assertEqual(event.get("exec_errno_name"), "ENOENT")
        self.assertEqual(event.get("exec_attempted_path"), attempted)
        self.assertEqual(event.get("cmd"), attempted)


if __name__ == "__main__":
    unittest.main()
