import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


DETECT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_forbidden.py"


def make_exec_event(ts: str) -> dict:
    return {
        "schema_version": "auditd.filtered.v1",
        "session_id": "session_1",
        "ts": ts,
        "source": "audit",
        "event_type": "exec",
        "cmd": "curl https://example.com",
        "cwd": "/work",
        "comm": "curl",
        "exe": "/usr/bin/curl",
        "pid": 200,
        "ppid": 1,
        "uid": 1001,
        "gid": 1001,
        "audit_seq": 42,
        "audit_key": "exec",
        "agent_owned": True,
    }


def make_net_summary_event(ts: str) -> dict:
    return {
        "schema_version": "ebpf.summary.v1",
        "session_id": "session_1",
        "ts": ts,
        "source": "ebpf",
        "event_type": "net_summary",
        "pid": 200,
        "ppid": 1,
        "uid": 1001,
        "gid": 1001,
        "comm": "curl",
        "dst_ip": "192.0.2.1",
        "dst_port": 25,
        "protocol": "tcp",
        "dns_names": ["example.com"],
        "connect_count": 1,
        "send_count": 1,
        "bytes_sent_total": 100,
        "ts_first": ts,
        "ts_last": ts,
    }


class ForbiddenDetectorTests(unittest.TestCase):
    def run_detector(self, audit_events: list[dict], ebpf_events: list[dict], policy: dict) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "filtered_audit.jsonl")
            ebpf_path = os.path.join(tmpdir, "filtered_ebpf_summary.jsonl")
            output_path = os.path.join(tmpdir, "filtered_alerts.jsonl")
            policy_path = os.path.join(tmpdir, "policy.json")

            Path(audit_path).write_text(
                "\n".join(json.dumps(ev) for ev in audit_events) + "\n",
                encoding="utf-8",
            )
            Path(ebpf_path).write_text(
                "\n".join(json.dumps(ev) for ev in ebpf_events) + "\n",
                encoding="utf-8",
            )
            Path(policy_path).write_text(json.dumps(policy), encoding="utf-8")

            config = {
                "policy": policy_path,
                "inputs": [
                    {"path": audit_path},
                    {"path": ebpf_path},
                ],
                "output": {"jsonl": output_path},
            }
            config_path = os.path.join(tmpdir, "config.json")
            Path(config_path).write_text(json.dumps(config), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(DETECT_SCRIPT), "--config", config_path],
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

    def test_exec_and_net_alerts(self) -> None:
        policy = {
            "schema_version": "forbidden.policy.v1",
            "policy": {
                "name": "test-pack",
                "defaults": {"action": "alert", "severity": "medium", "enabled": True},
                "rules": [
                    {
                        "id": "exec.curl",
                        "description": "Detect curl",
                        "event_type": "exec",
                        "match": {"comm": {"any": ["curl"]}},
                        "severity": "high",
                    },
                    {
                        "id": "net.smtp",
                        "description": "Detect SMTP port",
                        "event_type": "net_summary",
                        "match": {"dst_port": {"any": [25]}, "protocol": {"any": ["tcp"]}},
                    },
                ],
            },
        }

        events = self.run_detector(
            [make_exec_event("2026-02-02T00:00:01.000Z")],
            [make_net_summary_event("2026-02-02T00:00:02.000Z")],
            policy,
        )

        rule_ids = {event.get("rule_id") for event in events}
        self.assertIn("exec.curl", rule_ids)
        self.assertIn("net.smtp", rule_ids)
        for event in events:
            self.assertEqual(event.get("source"), "policy")
            self.assertEqual(event.get("event_type"), "alert")


if __name__ == "__main__":
    unittest.main()
