from __future__ import annotations

"""
Shared live-stack test harness for integration/regression/stress execution.

This module centralizes stack lifecycle and runtime assertions for tests that
must validate behavior produced by running collector/agent/harness services.
It intentionally focuses on live artifacts and live filtered outputs.
"""

import json
import os
import shlex
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any, Callable
from urllib import error, request


DEFAULT_HARNESS_CMD_TEMPLATE = "bash -lc {prompt}"
DEFAULT_CODEX_EXEC_TEMPLATE = "codex exec --skip-git-repo-check {prompt}"


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


@dataclass(frozen=True)
class ComposeFiles:
    base: Path
    overrides: tuple[Path, ...] = ()


class ComposeStack:
    """Utility wrapper for one isolated docker compose stack."""

    def __init__(
        self,
        *,
        root_dir: Path,
        temp_root: Path,
        test_slug: str,
        compose_files: ComposeFiles,
        env_overrides: dict[str, str] | None = None,
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
        if env_overrides:
            self.env.update(env_overrides)

        self.token = token
        self._up = False

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.harness_port}"

    @property
    def filtered_audit_path(self) -> Path:
        return self.log_root / "filtered_audit.jsonl"

    @property
    def filtered_ebpf_path(self) -> Path:
        return self.log_root / "filtered_ebpf.jsonl"

    @property
    def filtered_ebpf_summary_path(self) -> Path:
        return self.log_root / "filtered_ebpf_summary.jsonl"

    @property
    def timeline_path(self) -> Path:
        return self.log_root / "filtered_timeline.jsonl"

    def _compose_command(self, *args: str) -> list[str]:
        cmd: list[str] = ["docker", "compose", "-f", str(self.compose_files.base)]
        for override in self.compose_files.overrides:
            cmd.extend(["-f", str(override)])
        cmd.extend(args)
        return cmd

    def compose(
        self,
        *args: str,
        check: bool = True,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return run_cmd(
            self._compose_command(*args),
            cwd=self.root_dir,
            env=self.env,
            timeout=timeout,
            check=check,
        )

    def up(self) -> None:
        self.compose("up", "-d", "collector", "agent", "harness", timeout=240)
        self._up = True
        try:
            self.wait_for_services_running(("collector", "agent", "harness"), timeout_sec=90.0)
            self.wait_for_harness_ready()
        except AssertionError as exc:
            logs = self.capture_compose_logs()
            raise AssertionError(f"{exc}\n\nCompose logs:\n{logs}") from exc

    def down(self) -> None:
        if not self._up:
            return
        self.compose("down", "-v", check=False, timeout=120)
        self._up = False

    def capture_compose_logs(self) -> str:
        result = self.compose("logs", "--no-color", check=False, timeout=120)
        return (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")

    def running_services(self) -> set[str]:
        result = self.compose("ps", "--status", "running", "--services", check=False, timeout=30)
        return {
            line.strip()
            for line in (result.stdout or "").splitlines()
            if line.strip()
        }

    def wait_for_services_running(
        self,
        services: tuple[str, ...],
        *,
        timeout_sec: float = 60.0,
        interval_sec: float = 1.0,
    ) -> None:
        deadline = time.time() + timeout_sec
        last_running: set[str] = set()
        while time.time() < deadline:
            running = self.running_services()
            last_running = running
            missing = [svc for svc in services if svc not in running]
            if not missing:
                return
            time.sleep(interval_sec)
        missing = [svc for svc in services if svc not in last_running]
        raise AssertionError(
            f"Timed out waiting for running services={services}. "
            f"Missing={missing}, running={sorted(last_running)}."
        )

    def exec_service(
        self,
        service: str,
        *command: str,
        env: dict[str, str] | None = None,
        tty: bool = False,
        check: bool = True,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args: list[str] = ["exec"]
        if not tty:
            args.append("-T")
        if env:
            for key, value in env.items():
                args.extend(["-e", f"{key}={value}"])
        args.append(service)
        args.extend(command)
        return self.compose(*args, check=check, timeout=timeout)

    def wait_for(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_sec: float,
        message: str,
        interval_sec: float = 0.5,
    ) -> None:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(interval_sec)
        raise AssertionError(message)

    def wait_for_harness_ready(self, timeout_sec: float = 120.0) -> None:
        def _ready() -> bool:
            status, _ = self.request_json("GET", "/jobs/_")
            return status == 404

        self.wait_for(
            _ready,
            timeout_sec=timeout_sec,
            message=f"Harness did not become ready on {self.base_url}",
            interval_sec=1.0,
        )

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | str]:
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

    def wait_for_job(self, job_id: str, *, timeout_sec: float = 300.0) -> dict[str, Any]:
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

    def submit_and_wait(
        self,
        prompt: str,
        *,
        timeout_sec: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        job_id = self.submit_job(prompt, timeout_sec=timeout_sec)
        status = self.wait_for_job(job_id)
        return job_id, status

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

    def wait_for_jsonl_rows(
        self,
        path: Path,
        predicate: Callable[[list[dict[str, Any]]], bool],
        *,
        timeout_sec: float,
        message: str,
        interval_sec: float = 1.0,
    ) -> list[dict[str, Any]]:
        deadline = time.time() + timeout_sec
        last_rows: list[dict[str, Any]] = []
        while time.time() < deadline:
            rows = self.read_jsonl(path)
            last_rows = rows
            if predicate(rows):
                return rows
            time.sleep(interval_sec)
        raise AssertionError(f"{message}. Last row count={len(last_rows)} path={path}")

    def wait_for_timeline_rows(
        self,
        predicate: Callable[[list[dict[str, Any]]], bool],
        *,
        timeout_sec: float,
        message: str,
    ) -> list[dict[str, Any]]:
        return self.wait_for_jsonl_rows(
            self.timeline_path,
            predicate,
            timeout_sec=timeout_sec,
            message=message,
        )

    def wait_for_job_timeline_rows(
        self,
        job_id: str,
        *,
        timeout_sec: float = 120.0,
        required_path: str | None = None,
    ) -> list[dict[str, Any]]:
        def _matches(rows: list[dict[str, Any]]) -> bool:
            for row in rows:
                if row.get("job_id") != job_id:
                    continue
                if required_path is None:
                    return True
                details = row.get("details") or {}
                if isinstance(details, dict) and details.get("path") == required_path:
                    return True
            return False

        return self.wait_for_timeline_rows(
            _matches,
            timeout_sec=timeout_sec,
            message=f"Timeline rows for job_id={job_id} not observed",
        )

    def run_harness_tui(
        self,
        *,
        tui_cmd: str,
        tui_name: str,
        timeout_sec: float = 300.0,
    ) -> subprocess.CompletedProcess[str]:
        command = f"python3 /usr/local/bin/harness.py tui --tui-name {shlex.quote(tui_name)}"
        return self.exec_service(
            "harness",
            "script",
            "-qec",
            command,
            "/dev/null",
            env={"HARNESS_TUI_CMD": tui_cmd},
            tty=False,
            check=False,
            timeout=timeout_sec,
        )

    def host_log_path_from_container_path(self, container_path: str) -> Path:
        if not container_path.startswith("/logs/"):
            raise AssertionError(f"Unexpected container log path: {container_path}")
        return self.log_root / container_path.removeprefix("/logs/")
