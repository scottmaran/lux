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
SUMMARY_SCRIPT = ROOT_DIR / "collector" / "scripts" / "summarize_ebpf_logs.py"


def make_event(
    event_type: str,
    ts: str,
    net: dict | None = None,
    dns: dict | None = None,
    pid: int = 100,
    session_id: str = "session_1",
    job_id: str | None = None,
    comm: str = "tokio-runtime-w",
) -> dict:
    event = {
        "schema_version": "ebpf.filtered.v1",
        "session_id": session_id,
        "ts": ts,
        "source": "ebpf",
        "event_type": event_type,
        "pid": pid,
        "ppid": 1,
        "uid": 1001,
        "gid": 1001,
        "comm": comm,
        "cgroup_id": "0x0000000000000001",
        "syscall_result": 0,
        "agent_owned": True,
    }
    if job_id:
        event["job_id"] = job_id
    if net is not None:
        event["net"] = net
    if dns is not None:
        event["dns"] = dns
    return event


class TestEbpfSummary(unittest.TestCase):
    def run_summary(self, events: list[dict], config_overrides: dict | None = None) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "filtered_ebpf.jsonl")
            output_path = os.path.join(tmpdir, "filtered_ebpf_summary.jsonl")
            config_path = os.path.join(tmpdir, "config.json")

            Path(input_path).write_text(
                "\n".join(json.dumps(ev) for ev in events) + "\n",
                encoding="utf-8",
            )
            config = {
                "schema_version": "ebpf.summary.v1",
                "input": {"jsonl": input_path},
                "output": {"jsonl": output_path},
                "burst_gap_sec": 5,
            }
            if config_overrides:
                config.update(config_overrides)
            Path(config_path).write_text(json.dumps(config), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SUMMARY_SCRIPT), "--config", config_path],
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

    def test_burst_grouping_and_dns_within_window(self) -> None:
        events = [
            make_event(
                "dns_response",
                "2026-01-22T00:00:01.000Z",
                dns={
                    "query_name": "example.com",
                    "answers": ["1.2.3.4"],
                },
            ),
            make_event(
                "net_connect",
                "2026-01-22T00:00:02.500Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp"},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:02.000Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp", "bytes": 10},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:03.000Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp", "bytes": 5},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:10.500Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp", "bytes": 7},
            ),
            make_event(
                "dns_response",
                "2026-01-22T00:00:10.500Z",
                dns={
                    "query_name": "example2.com",
                    "answers": ["1.2.3.4"],
                },
            ),
            make_event(
                "net_connect",
                "2026-01-22T00:00:10.500Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp"},
            ),
        ]

        rows = self.run_summary(events, {"dns_lookback_sec": 2})
        summary_rows = [row for row in rows if row.get("event_type") == "net_summary"]
        self.assertEqual(len(summary_rows), 2)

        first = summary_rows[0]
        self.assertEqual(first["dst_ip"], "1.2.3.4")
        self.assertEqual(first["dst_port"], 443)
        self.assertEqual(first["send_count"], 2)
        self.assertEqual(first["bytes_sent_total"], 15)
        self.assertEqual(first["connect_count"], 1)
        self.assertEqual(first["dns_names"], ["example.com"])
        self.assertEqual(first["ts_first"], "2026-01-22T00:00:02.000Z")
        self.assertEqual(first["ts_last"], "2026-01-22T00:00:03.000Z")

        second = summary_rows[1]
        self.assertEqual(second["send_count"], 1)
        self.assertEqual(second["bytes_sent_total"], 7)
        self.assertEqual(second["connect_count"], 1)
        self.assertEqual(second["dns_names"], ["example2.com"])
        self.assertEqual(second["ts_first"], "2026-01-22T00:00:10.500Z")
        self.assertEqual(second["ts_last"], "2026-01-22T00:00:10.500Z")

    def test_suppression_thresholds(self) -> None:
        events = [
            make_event(
                "net_send",
                "2026-01-22T00:00:01.000Z",
                net={"dst_ip": "9.9.9.9", "dst_port": 443, "protocol": "tcp", "bytes": 50},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:10.000Z",
                net={"dst_ip": "9.9.9.9", "dst_port": 443, "protocol": "tcp", "bytes": 150},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:20.000Z",
                net={"dst_ip": "9.9.9.9", "dst_port": 443, "protocol": "tcp", "bytes": 30},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:20.500Z",
                net={"dst_ip": "9.9.9.9", "dst_port": 443, "protocol": "tcp", "bytes": 30},
            ),
        ]

        rows = self.run_summary(
            events,
            {"min_send_count": 1, "min_bytes_sent_total": 100},
        )
        summary_rows = [row for row in rows if row.get("event_type") == "net_summary"]
        self.assertEqual(len(summary_rows), 2)
        self.assertEqual(summary_rows[0]["send_count"], 1)
        self.assertEqual(summary_rows[1]["send_count"], 2)

    def test_connects_only_do_not_emit_summary(self) -> None:
        events = [
            make_event(
                "net_connect",
                "2026-01-22T00:00:02.000Z",
                net={"dst_ip": "2.2.2.2", "dst_port": 443, "protocol": "tcp"},
            )
        ]
        rows = self.run_summary(events)
        summary_rows = [row for row in rows if row.get("event_type") == "net_summary"]
        self.assertEqual(len(summary_rows), 0)

    def test_sorting_by_ts_first(self) -> None:
        events = [
            make_event(
                "net_send",
                "2026-01-22T00:00:03.000Z",
                net={"dst_ip": "3.3.3.3", "dst_port": 443, "protocol": "tcp", "bytes": 5},
                pid=300,
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:01.500Z",
                net={"dst_ip": "1.1.1.1", "dst_port": 443, "protocol": "tcp", "bytes": 5},
                pid=100,
            ),
        ]
        rows = self.run_summary(events)
        summary_rows = [row for row in rows if row.get("event_type") == "net_summary"]
        self.assertEqual(len(summary_rows), 2)
        self.assertEqual(summary_rows[0]["dst_ip"], "1.1.1.1")
        self.assertEqual(summary_rows[1]["dst_ip"], "3.3.3.3")

    def test_unix_connect_pass_through(self) -> None:
        events = [
            make_event(
                "unix_connect",
                "2026-01-22T00:00:04.000Z",
                comm="dbus-daemon",
            )
        ]
        rows = self.run_summary(events)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "unix_connect")
        self.assertEqual(rows[0]["schema_version"], "ebpf.summary.v1")


if __name__ == "__main__":
    unittest.main()
