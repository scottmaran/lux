import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT_DIR = Path(__file__).resolve().parents[3]
MERGE_SCRIPT = ROOT_DIR / "collector" / "scripts" / "merge_filtered_logs.py"


def make_audit_event(ts: str, session_id: str, job_id: str | None = None) -> dict:
    event = {
        "schema_version": "auditd.filtered.v1",
        "session_id": session_id,
        "ts": ts,
        "source": "audit",
        "event_type": "exec",
        "cmd": "pwd",
        "cwd": "/work",
        "comm": "bash",
        "exe": "/usr/bin/bash",
        "pid": 100,
        "ppid": 1,
        "uid": 1001,
        "gid": 1001,
        "audit_seq": 42,
        "audit_key": "exec",
        "agent_owned": True,
    }
    if job_id:
        event["job_id"] = job_id
    return event


def make_ebpf_event(ts: str, session_id: str, job_id: str | None = None) -> dict:
    event = {
        "schema_version": "ebpf.filtered.v1",
        "session_id": session_id,
        "ts": ts,
        "source": "ebpf",
        "event_type": "net_connect",
        "comm": "tokio-runtime-w",
        "pid": 101,
        "ppid": 100,
        "uid": 1001,
        "gid": 1001,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "net": {
            "protocol": "tcp",
            "family": "ipv4",
            "src_ip": "172.18.0.3",
            "src_port": 44444,
            "dst_ip": "93.184.216.34",
            "dst_port": 443,
        },
        "agent_owned": True,
    }
    if job_id:
        event["job_id"] = job_id
    return event


class TestMergeFiltered(unittest.TestCase):
    def run_merge(self, audit_events: list[dict], ebpf_events: list[dict], config: dict) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "filtered_audit.jsonl")
            ebpf_path = os.path.join(tmpdir, "filtered_ebpf.jsonl")
            output_path = os.path.join(tmpdir, "filtered_timeline.jsonl")

            Path(audit_path).write_text(
                "\n".join(json.dumps(ev) for ev in audit_events) + "\n",
                encoding="utf-8",
            )
            Path(ebpf_path).write_text(
                "\n".join(json.dumps(ev) for ev in ebpf_events) + "\n",
                encoding="utf-8",
            )

            cfg = dict(config)
            cfg["inputs"] = [
                {"path": audit_path, "source": "audit"},
                {"path": ebpf_path, "source": "ebpf"},
            ]
            cfg["output"] = {"jsonl": output_path}

            config_path = os.path.join(tmpdir, "config.json")
            Path(config_path).write_text(json.dumps(cfg), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(MERGE_SCRIPT), "--config", config_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr.strip())

            if not os.path.exists(output_path):
                return []
            lines = Path(output_path).read_text(encoding="utf-8").splitlines()
            return [json.loads(line) for line in lines if line.strip()]

    def base_config(self) -> dict:
        return {
            "schema_version": "timeline.filtered.v1",
            "sorting": {"strategy": "ts_source_pid"},
        }

    def test_merge_orders_and_normalizes(self) -> None:
        audit_event = make_audit_event("2026-01-22T00:00:01.000Z", "session_1")
        ebpf_event = make_ebpf_event("2026-01-22T00:00:00.500Z", "session_1")

        rows = self.run_merge([audit_event], [ebpf_event], self.base_config())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source"], "ebpf")
        self.assertEqual(rows[1]["source"], "audit")
        self.assertEqual(rows[0]["schema_version"], "timeline.filtered.v1")
        self.assertIn("details", rows[0])
        self.assertIn("net", rows[0]["details"])
        self.assertIn("cmd", rows[1]["details"])

    def test_merge_preserves_session_and_job(self) -> None:
        audit_event = make_audit_event("2026-01-22T00:00:02.000Z", "unknown", job_id="job_1")
        ebpf_event = make_ebpf_event("2026-01-22T00:00:03.000Z", "session_2")

        rows = self.run_merge([audit_event], [ebpf_event], self.base_config())
        audit_row = next(row for row in rows if row["source"] == "audit")
        ebpf_row = next(row for row in rows if row["source"] == "ebpf")
        self.assertEqual(audit_row["job_id"], "job_1")
        self.assertEqual(audit_row["session_id"], "unknown")
        self.assertEqual(ebpf_row["session_id"], "session_2")

    def test_source_fallback(self) -> None:
        audit_event = make_audit_event("2026-01-22T00:00:04.000Z", "session_3")
        audit_event.pop("source", None)

        rows = self.run_merge([audit_event], [], self.base_config())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "audit")


if __name__ == "__main__":
    unittest.main()
