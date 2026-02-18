from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import pytest

from tests.support.integration_stack import run_cmd


pytestmark = pytest.mark.integration


ROOT_DIR = Path(__file__).resolve().parents[2]
COLLECTOR_IMAGE = "lux-test-collector:local"


def _tail(path: Path, *, lines: int = 40) -> str:
    if not path.exists():
        return "<missing>"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not content:
        return "<empty>"
    return "\n".join(content[-lines:])


def _collector_logs(container_name: str) -> str:
    result = run_cmd(
        ["docker", "logs", container_name],
        cwd=ROOT_DIR,
        check=False,
        timeout=30,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    return f"stdout:\n{stdout}\n\nstderr:\n{stderr}"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _audit_has_exec_signal(path: Path) -> bool:
    content = _read_text(path)
    return "type=SYSCALL" in content and 'key="exec"' in content


def _audit_has_workspace_path_signal(path: Path) -> bool:
    content = _read_text(path)
    return "type=PATH" in content and "/work/" in content


def _ebpf_event_types(path: Path) -> set[str]:
    event_types: set[str] = set()
    if not path.exists():
        return event_types
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = payload.get("event_type")
        if isinstance(event_type, str):
            event_types.add(event_type)
    return event_types


def test_collector_only_raw_log_smoke_includes_fs_net_dns_unix_signals(
    tmp_path: Path,
    build_local_images,
) -> None:
    """
    Collector-only smoke test (no harness/agent orchestration).

    Validates the behavior covered by legacy collector smoke scripts:
    - collector starts with privileged host mounts,
    - filesystem activity appears in raw audit.log,
    - DNS/TCP and unix socket activity appears in raw ebpf.jsonl.
    """
    workspace = tmp_path / "workspace"
    logs = tmp_path / "logs"
    workspace.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    collector_name = f"lux-collector-smoke-{uuid.uuid4().hex[:10]}"
    audit_path = logs / "audit.log"
    ebpf_path = logs / "ebpf.jsonl"

    run_cmd(
        [
            "docker",
            "run",
            "-d",
            "--name",
            collector_name,
            "--pid=host",
            "--cgroupns=host",
            "--privileged",
            "-e",
            "COLLECTOR_AUDIT_LOG=/logs/audit.log",
            "-e",
            "COLLECTOR_EBPF_OUTPUT=/logs/ebpf.jsonl",
            "-v",
            f"{logs}:/logs:rw",
            "-v",
            f"{workspace}:/work:ro",
            "-v",
            "/sys/fs/bpf:/sys/fs/bpf:rw",
            "-v",
            "/sys/kernel/tracing:/sys/kernel/tracing:rw",
            "-v",
            "/sys/kernel/debug:/sys/kernel/debug:rw",
            COLLECTOR_IMAGE,
        ],
        cwd=ROOT_DIR,
        timeout=60,
    )

    try:
        time.sleep(3)

        run_cmd(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{workspace}:/work",
                "alpine",
                "sh",
                "-c",
                "echo hi > /work/a.txt; mv /work/a.txt /work/b.txt; chmod 600 /work/b.txt; rm /work/b.txt",
            ],
            cwd=ROOT_DIR,
            timeout=60,
        )

        run_cmd(
            [
                "docker",
                "run",
                "--rm",
                "alpine",
                "sh",
                "-c",
                (
                    "apk add --no-cache curl bind-tools >/dev/null; "
                    "nslookup example.com >/dev/null || true; "
                    "curl -I --max-time 8 https://example.com >/dev/null || true"
                ),
            ],
            cwd=ROOT_DIR,
            timeout=90,
        )

        run_cmd(
            [
                "docker",
                "run",
                "--rm",
                "python:3-alpine",
                "sh",
                "-c",
                (
                    "python - <<'PY'\n"
                    "import os, socket, threading, time\n"
                    "path = '/tmp/ipc.sock'\n"
                    "try:\n"
                    "    os.unlink(path)\n"
                    "except FileNotFoundError:\n"
                    "    pass\n"
                    "server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
                    "server.bind(path)\n"
                    "server.listen(1)\n"
                    "def accept():\n"
                    "    conn, _ = server.accept()\n"
                    "    conn.close()\n"
                    "    server.close()\n"
                    "threading.Thread(target=accept, daemon=True).start()\n"
                    "client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
                    "client.connect(path)\n"
                    "client.close()\n"
                    "time.sleep(0.1)\n"
                    "PY"
                ),
            ],
            cwd=ROOT_DIR,
            timeout=90,
        )

        deadline = time.time() + 90
        last_audit_tail = ""
        last_event_types: set[str] = set()
        while time.time() < deadline:
            last_audit_tail = _tail(audit_path)
            last_event_types = _ebpf_event_types(ebpf_path)

            has_audit_exec = _audit_has_exec_signal(audit_path)
            has_audit_fs = _audit_has_workspace_path_signal(audit_path)
            has_net_or_dns = bool(last_event_types.intersection({"net_connect", "net_send", "dns_query", "dns_response"}))
            has_unix = "unix_connect" in last_event_types
            if has_audit_exec and has_audit_fs and has_net_or_dns and has_unix:
                return

            time.sleep(1.0)

        raise AssertionError(
            "collector-only raw smoke did not observe required raw signals in time.\n"
            f"audit_tail:\n{last_audit_tail}\n\n"
            f"ebpf_event_types={sorted(last_event_types)}\n\n"
            f"collector_logs:\n{_collector_logs(collector_name)}"
        )
    finally:
        run_cmd(
            ["docker", "rm", "-f", collector_name],
            cwd=ROOT_DIR,
            check=False,
            timeout=30,
        )
