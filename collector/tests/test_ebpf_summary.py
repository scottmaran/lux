import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SUMMARY_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "summarize_ebpf_logs.py"


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


class EbpfSummaryTests(unittest.TestCase):
    def run_summary(self, events: list[dict]) -> list[dict]:
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
            }
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

    def test_summary_aggregates_and_maps_dns(self) -> None:
        events = [
            make_event(
                "dns_response",
                "2026-01-22T00:00:00.900Z",
                dns={
                    "query_name": "chatgpt.com",
                    "answers": ["1.2.3.4"],
                },
            ),
            make_event(
                "net_connect",
                "2026-01-22T00:00:01.000Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp"},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:01.100Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp", "bytes": 10},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:01.200Z",
                net={"dst_ip": "1.2.3.4", "dst_port": 443, "protocol": "tcp", "bytes": 5},
            ),
            make_event(
                "net_send",
                "2026-01-22T00:00:01.250Z",
                net={"dst_ip": "127.0.0.11", "dst_port": 53, "protocol": "udp", "bytes": 30},
            ),
        ]

        rows = self.run_summary(events)
        summary_rows = [row for row in rows if row.get("event_type") == "net_summary"]
        self.assertEqual(len(summary_rows), 1)
        row = summary_rows[0]
        self.assertEqual(row["dst_ip"], "1.2.3.4")
        self.assertEqual(row["dst_port"], 443)
        self.assertEqual(row["connect_attempts"], 1)
        self.assertEqual(row["send_count"], 2)
        self.assertEqual(row["bytes_sent_total"], 15)
        self.assertEqual(row["dns_names"], ["chatgpt.com"])
        self.assertEqual(row["ts_first"], "2026-01-22T00:00:01.000Z")
        self.assertEqual(row["ts_last"], "2026-01-22T00:00:01.200Z")

    def test_summary_emits_connect_without_send(self) -> None:
        events = [
            make_event(
                "net_connect",
                "2026-01-22T00:00:02.000Z",
                net={"dst_ip": "2.2.2.2", "dst_port": 443, "protocol": "tcp"},
            )
        ]
        rows = self.run_summary(events)
        summary_rows = [row for row in rows if row.get("event_type") == "net_summary"]
        self.assertEqual(len(summary_rows), 1)
        row = summary_rows[0]
        self.assertEqual(row["send_count"], 0)
        self.assertEqual(row["bytes_sent_total"], 0)

    def test_sorting_by_ts_first(self) -> None:
        events = [
            make_event(
                "net_connect",
                "2026-01-22T00:00:03.000Z",
                net={"dst_ip": "3.3.3.3", "dst_port": 443, "protocol": "tcp"},
                pid=300,
            ),
            make_event(
                "net_connect",
                "2026-01-22T00:00:01.500Z",
                net={"dst_ip": "1.1.1.1", "dst_port": 443, "protocol": "tcp"},
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
