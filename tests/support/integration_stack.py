from __future__ import annotations

"""
Shared integration-test harness for isolated Docker stacks and deterministic
collector pipeline execution.

This module centralizes the mechanics that integration/regression/stress tests
should not re-implement:
- compose stack lifecycle (`up`/`down`) with per-test isolation,
- harness API polling and job lifecycle helpers, and
- synthetic log injection + collector script orchestration for deterministic
  attribution/filter/merge assertions.
"""

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from http.client import RemoteDisconnected
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

import yaml


DEFAULT_HARNESS_CMD_TEMPLATE = "bash -lc {prompt}"


class CommandError(RuntimeError):
    """Raised when a shell command exits non-zero."""

    def __init__(self, cmd: list[str], result: subprocess.CompletedProcess[str]) -> None:
        joined = " ".join(cmd)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        super().__init__(
            f"Command failed ({result.returncode}): {joined}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
        self.cmd = cmd
        self.result = result


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise CommandError(cmd, result)
    return result


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


@dataclass
class ComposeFiles:
    base: Path
    override: Path | None = None


class ComposeStack:
    """Utility wrapper for an isolated compose stack used by integration/stress tests."""

    def __init__(
        self,
        *,
        root_dir: Path,
        temp_root: Path,
        test_slug: str,
        compose_files: ComposeFiles,
    ) -> None:
        self.root_dir = root_dir
        self.temp_root = temp_root
        self.log_root = temp_root / "logs"
        self.workspace_root = temp_root / "workspace"
        self.log_root.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.compose_files = compose_files
        self.project_name = f"lasso-test-{test_slug}-{uuid.uuid4().hex[:8]}"
        self.harness_port = find_free_port()
        token = f"token-{uuid.uuid4().hex}"

        self.env = os.environ.copy()
        self.env.update(
            {
                "COMPOSE_PROJECT_NAME": self.project_name,
                "HARNESS_API_TOKEN": token,
                "HARNESS_RUN_CMD_TEMPLATE": DEFAULT_HARNESS_CMD_TEMPLATE,
                "LASSO_LOG_ROOT": str(self.log_root),
                "LASSO_WORKSPACE_ROOT": str(self.workspace_root),
                "LASSO_VERSION": "local",
                "HARNESS_HOST_PORT": str(self.harness_port),
            }
        )
        self.token = token
        self._up = False

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.harness_port}"

    @property
    def timeline_path(self) -> Path:
        return self.log_root / "filtered_timeline.jsonl"

    def compose(self, *args: str, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.compose_files.base),
            *args,
        ]
        if self.compose_files.override:
            cmd = [
                "docker",
                "compose",
                "-f",
                str(self.compose_files.base),
                "-f",
                str(self.compose_files.override),
                *args,
            ]
        return run_cmd(cmd, cwd=self.root_dir, env=self.env, timeout=timeout, check=check)

    def up(self) -> None:
        self.compose("up", "-d", "collector", "agent", "harness", timeout=180)
        self._up = True
        self.wait_for_harness_ready()

    def down(self) -> None:
        if not self._up:
            return
        self.compose("down", "-v", check=False, timeout=120)
        self._up = False

    def capture_compose_logs(self) -> str:
        result = self.compose("logs", "--no-color", check=False, timeout=120)
        return (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")

    def wait_for(self, predicate: Callable[[], bool], *, timeout_sec: float, message: str, interval_sec: float = 0.5) -> None:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(interval_sec)
        raise AssertionError(message)

    def wait_for_harness_ready(self, timeout_sec: float = 90.0) -> None:
        def _ready() -> bool:
            status, _ = self.request_json("GET", "/jobs/_")
            return status == 404

        self.wait_for(
            _ready,
            timeout_sec=timeout_sec,
            message=f"Harness did not become ready on {self.base_url}",
            interval_sec=1.0,
        )

    def request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | str]:
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Harness-Token": self.token,
            },
        )
        try:
            with request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
                return resp.status, parsed
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = body
            return exc.code, parsed
        except (error.URLError, TimeoutError, ConnectionRefusedError, RemoteDisconnected):
            return 0, {}

    def submit_job(self, prompt: str, *, timeout_sec: int | None = None) -> str:
        payload: dict[str, Any] = {"prompt": prompt}
        if timeout_sec:
            payload["timeout_sec"] = timeout_sec
        status, body = self.request_json("POST", "/run", payload)
        if status != 202:
            raise AssertionError(f"Expected 202 from /run, got {status}: {body}")
        if not isinstance(body, dict) or "job_id" not in body:
            raise AssertionError(f"Malformed /run response payload: {body}")
        return str(body["job_id"])

    def get_job(self, job_id: str) -> dict[str, Any]:
        status, body = self.request_json("GET", f"/jobs/{job_id}")
        if status != 200 or not isinstance(body, dict):
            raise AssertionError(f"Failed to read job {job_id}: {status} {body}")
        return body

    def wait_for_job(self, job_id: str, *, timeout_sec: float = 240.0) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        last: dict[str, Any] | None = None
        while time.time() < deadline:
            status = self.get_job(job_id)
            last = status
            state = status.get("status")
            if state in {"complete", "failed"}:
                return status
            time.sleep(1.0)
        raise AssertionError(f"Timed out waiting for job {job_id}. Last status: {last}")

    def submit_and_wait(self, prompt: str, *, timeout_sec: int | None = None) -> tuple[str, dict[str, Any]]:
        job_id = self.submit_job(prompt, timeout_sec=timeout_sec)
        status = self.wait_for_job(job_id)
        return job_id, status

    def append_ebpf_event(self, event: dict[str, Any]) -> None:
        """
        Append one eBPF JSON event into the stack's live collector input file.

        Why this exists:
        - Some integration-style scenarios need to inject a single runtime-like
          eBPF record into `/logs/ebpf.jsonl` without rebuilding whole fixtures.

        Where it is typically called:
        - Integration/regression/stress tests that are exercising the running
          compose stack and want direct event injection.

        Where `event` is typically generated:
        - `tests.support.synthetic_logs.make_net_send_event(...)`, or a
          hand-crafted dict that follows the `ebpf.v1` schema.
        """
        ebpf_path = self.log_root / "ebpf.jsonl"
        with ebpf_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    def wait_for_timeline_rows(self, predicate: Callable[[list[dict[str, Any]]], bool], *, timeout_sec: float, message: str) -> list[dict[str, Any]]:
        """
        Poll timeline output until a condition is met or timeout expires.

        The collector/harness pipeline is asynchronous: tests may finish job
        execution before `filtered_timeline.jsonl` has all expected rows. This
        helper prevents race-condition flakiness by repeatedly reading timeline
        rows until the caller-defined predicate becomes true.
        """
        deadline = time.time() + timeout_sec
        last_rows: list[dict[str, Any]] = []
        while time.time() < deadline:
            rows = self.read_jsonl(self.timeline_path)
            last_rows = rows
            if predicate(rows):
                return rows
            time.sleep(1.0)
        raise AssertionError(f"{message}. Last timeline rows: {len(last_rows)}")

    def run_collector_pipeline(
        self,
        *,
        audit_lines: list[str],
        ebpf_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Run collector scripts deterministically over provided synthetic logs."""
        ebpf_events = ebpf_events or []

        audit_log = self.log_root / "audit.synthetic.log"
        ebpf_log = self.log_root / "ebpf.synthetic.jsonl"
        filtered_audit = self.log_root / "filtered_audit.synthetic.jsonl"
        filtered_ebpf = self.log_root / "filtered_ebpf.synthetic.jsonl"
        filtered_summary = self.log_root / "filtered_ebpf_summary.synthetic.jsonl"
        timeline = self.log_root / "filtered_timeline.synthetic.jsonl"

        audit_log.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
        ebpf_log.write_text(
            "\n".join(json.dumps(event, separators=(",", ":")) for event in ebpf_events)
            + ("\n" if ebpf_events else ""),
            encoding="utf-8",
        )

        audit_cfg = deepcopy(
            yaml.safe_load((self.root_dir / "collector" / "config" / "filtering.yaml").read_text(encoding="utf-8"))
        )
        audit_cfg["input"] = {"audit_log": str(audit_log)}
        audit_cfg["output"] = {"jsonl": str(filtered_audit)}
        audit_cfg["sessions_dir"] = str(self.log_root / "sessions")
        audit_cfg["jobs_dir"] = str(self.log_root / "jobs")

        ebpf_cfg = deepcopy(
            yaml.safe_load((self.root_dir / "collector" / "config" / "ebpf_filtering.yaml").read_text(encoding="utf-8"))
        )
        ebpf_cfg["input"] = {"audit_log": str(audit_log), "ebpf_log": str(ebpf_log)}
        ebpf_cfg["output"] = {"jsonl": str(filtered_ebpf)}
        ebpf_cfg["sessions_dir"] = str(self.log_root / "sessions")
        ebpf_cfg["jobs_dir"] = str(self.log_root / "jobs")

        summary_cfg = deepcopy(
            yaml.safe_load((self.root_dir / "collector" / "config" / "ebpf_summary.yaml").read_text(encoding="utf-8"))
        )
        summary_cfg["input"] = {"jsonl": str(filtered_ebpf)}
        summary_cfg["output"] = {"jsonl": str(filtered_summary)}

        merge_cfg = deepcopy(
            yaml.safe_load((self.root_dir / "collector" / "config" / "merge_filtering.yaml").read_text(encoding="utf-8"))
        )
        merge_cfg["inputs"] = [
            {"path": str(filtered_audit), "source": "audit"},
            {"path": str(filtered_summary), "source": "ebpf"},
        ]
        merge_cfg["output"] = {"jsonl": str(timeline)}

        scripts = [
            (self.root_dir / "collector" / "scripts" / "filter_audit_logs.py", audit_cfg, self.log_root / "audit.config.yaml"),
            (self.root_dir / "collector" / "scripts" / "filter_ebpf_logs.py", ebpf_cfg, self.log_root / "ebpf.config.yaml"),
            (self.root_dir / "collector" / "scripts" / "summarize_ebpf_logs.py", summary_cfg, self.log_root / "summary.config.yaml"),
            (self.root_dir / "collector" / "scripts" / "merge_filtered_logs.py", merge_cfg, self.log_root / "merge.config.yaml"),
        ]
        for script, config, path in scripts:
            # For each collector stage:
            # 1) Materialize a per-stage config file under this test's temp log
            #    root so failures are reproducible with exact inputs.
            # 2) Execute the stage as a subprocess using the repo's Python
            #    interpreter, matching production CLI behavior:
            #    - filter_audit_logs.py: raw audit -> filtered audit JSONL
            #    - filter_ebpf_logs.py: raw eBPF (+ audit ownership) -> filtered eBPF JSONL
            #    - summarize_ebpf_logs.py: filtered eBPF -> net_summary rows
            #    - merge_filtered_logs.py: audit + summary -> timeline JSONL
            path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--config", str(path)],
                cwd=str(self.root_dir),
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise AssertionError(
                    f"Collector script failed: {script}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                )

        return {
            "filtered_audit": self.read_jsonl(filtered_audit),
            "filtered_ebpf": self.read_jsonl(filtered_ebpf),
            "filtered_ebpf_summary": self.read_jsonl(filtered_summary),
            "timeline": self.read_jsonl(timeline),
        }
