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
from datetime import datetime, timezone
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any, Callable
from urllib import error, request


DEFAULT_HARNESS_CMD_TEMPLATE = "bash -lc {prompt}"
DEFAULT_CODEX_EXEC_TEMPLATE = "codex exec --skip-git-repo-check {prompt}"
HEARTBEAT_MAX_SEND_COUNT = 4
HEARTBEAT_MAX_BYTES_SENT = 4096


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def timeline_row_epoch_seconds(row: dict[str, Any]) -> float | None:
    """Return row timestamp as epoch seconds, or None for invalid/missing timestamps."""
    parsed = _parse_iso_timestamp(row.get("ts"))
    return None if parsed is None else parsed.timestamp()


def is_heartbeat_like_signal_row(row: dict[str, Any]) -> bool:
    """
    Classify low-signal periodic eBPF traffic summaries that should not reset
    activity clocks used to detect "prompt finished" quiescence.
    """
    if row.get("source") != "ebpf" or row.get("event_type") != "net_summary":
        return False
    details = row.get("details")
    if not isinstance(details, dict):
        return False

    connect_count = _coerce_int(details.get("connect_count"))
    send_count = _coerce_int(details.get("send_count"))
    bytes_sent_total = _coerce_int(details.get("bytes_sent_total"))
    if connect_count is None or send_count is None or bytes_sent_total is None:
        return False

    return (
        connect_count == 0
        and send_count <= HEARTBEAT_MAX_SEND_COUNT
        and bytes_sent_total <= HEARTBEAT_MAX_BYTES_SENT
    )


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


@dataclass(frozen=True)
class RunningTuiProcess:
    """Handle for an in-flight harness TUI invocation started via docker compose."""

    process: subprocess.Popen[bytes]
    command: tuple[str, ...]
    tui_name: str
    driver_stdout_path: Path
    driver_stderr_path: Path


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
        self._chmod_bind_mount_dir_writable(self.log_root)
        self._chmod_bind_mount_dir_writable(self.workspace_root)

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

    @staticmethod
    def _chmod_bind_mount_dir_writable(path: Path) -> None:
        """
        Ensure docker bind-mount roots are writable by non-root service users.

        Linux CI runners enforce UID/GID permissions on bind mounts, unlike some
        Docker Desktop setups that can appear more permissive.
        """
        path.chmod(0o777)

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
            logs = self.capture_compose_logs("harness", "agent")
            if not logs.strip():
                logs = self.capture_compose_logs()
            mount_info = self._mount_root_diagnostics()
            raise AssertionError(
                f"{exc}\n\nMount roots:\n{mount_info}\n\nCompose logs:\n{logs}"
            ) from exc

    def down(self) -> None:
        if not self._up:
            return
        self.compose("down", "-v", check=False, timeout=120)
        self._up = False

    def capture_compose_logs(self, *services: str) -> str:
        args: list[str] = ["logs", "--no-color"]
        args.extend(services)
        result = self.compose(*args, check=False, timeout=120)
        return (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")

    def running_services(self) -> set[str]:
        result = self.compose("ps", "--status", "running", "--services", check=False, timeout=30)
        return {
            line.strip()
            for line in (result.stdout or "").splitlines()
            if line.strip()
        }

    def service_states(self) -> dict[str, dict[str, Any]]:
        """
        Return current docker compose service states keyed by compose service name.

        Uses `docker compose ps --all --format json` and tolerates both:
        - a JSON array payload, and
        - newline-delimited JSON object rows.
        """
        result = self.compose("ps", "--all", "--format", "json", check=False, timeout=30)
        raw = (result.stdout or "").strip()
        if not raw:
            return {}

        rows: list[dict[str, Any]] = []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, list):
            rows = [row for row in parsed if isinstance(row, dict)]
        elif isinstance(parsed, dict):
            rows = [parsed]
        else:
            for line in raw.splitlines():
                item = line.strip()
                if not item:
                    continue
                try:
                    payload = json.loads(item)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)

        states: dict[str, dict[str, Any]] = {}
        for row in rows:
            service = row.get("Service") or row.get("service")
            if not isinstance(service, str) or not service:
                continue
            state = row.get("State") or row.get("state") or "unknown"
            status = row.get("Status") or row.get("status") or ""
            states[service] = {
                "state": str(state).strip().lower(),
                "status": str(status).strip(),
                "exit_code": row.get("ExitCode", row.get("exit_code")),
            }
        return states

    def _format_service_state_map(
        self,
        states: dict[str, dict[str, Any]],
        services: tuple[str, ...],
    ) -> str:
        rendered: list[str] = []
        for service in services:
            info = states.get(service)
            if not info:
                rendered.append(f"{service}=<missing>")
                continue
            rendered.append(
                f"{service}="
                f"{info.get('state')}("
                f"exit_code={info.get('exit_code')}, "
                f"status={info.get('status')!r})"
            )
        return ", ".join(rendered)

    def _mount_root_diagnostics(self) -> str:
        lines: list[str] = []
        for name, path in (("log_root", self.log_root), ("workspace_root", self.workspace_root)):
            if not path.exists():
                lines.append(f"{name}={path} <missing>")
                continue
            stat = path.stat()
            lines.append(
                f"{name}={path} "
                f"mode={oct(stat.st_mode & 0o777)} "
                f"uid={stat.st_uid} gid={stat.st_gid}"
            )
        return "\n".join(lines)

    def wait_for_services_running(
        self,
        services: tuple[str, ...],
        *,
        timeout_sec: float = 60.0,
        interval_sec: float = 1.0,
    ) -> None:
        terminal_states = {"dead", "exited"}
        deadline = time.time() + timeout_sec
        last_running: set[str] = set()
        last_states: dict[str, dict[str, Any]] = {}
        while time.time() < deadline:
            running = self.running_services()
            states = self.service_states()
            last_running = running
            last_states = states
            missing = [svc for svc in services if svc not in running]
            if not missing:
                return

            failed = {
                service: info
                for service, info in states.items()
                if service in services and str(info.get("state", "")).lower() in terminal_states
            }
            if failed:
                state_map = self._format_service_state_map(states, services)
                raise AssertionError(
                    "Required service entered terminal state before startup completed. "
                    f"failed={sorted(failed)} running={sorted(running)} states=[{state_map}]"
                )
            time.sleep(interval_sec)
        missing = [svc for svc in services if svc not in last_running]
        state_map = self._format_service_state_map(last_states, services)
        raise AssertionError(
            f"Timed out waiting for running services={services}. "
            f"Missing={missing}, running={sorted(last_running)}, states=[{state_map}]."
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

    def session_stdout_path(self, session_id: str) -> Path:
        return self.log_root / "sessions" / session_id / "stdout.log"

    def _session_activity_snapshot(self, session_id: str) -> dict[str, Any]:
        stdout_path = self.session_stdout_path(session_id)
        stdout_epoch = stdout_path.stat().st_mtime if stdout_path.exists() else None

        session_rows = [row for row in self.read_jsonl(self.timeline_path) if row.get("session_id") == session_id]
        latest_any_epoch: float | None = None
        latest_any_ts: str | None = None
        latest_signal_epoch: float | None = None
        latest_signal_ts: str | None = None
        heartbeat_row_count = 0
        non_heartbeat_row_count = 0

        for row in session_rows:
            ts_epoch = timeline_row_epoch_seconds(row)
            if ts_epoch is None:
                continue
            if latest_any_epoch is None or ts_epoch >= latest_any_epoch:
                latest_any_epoch = ts_epoch
                latest_any_ts = str(row.get("ts"))

            if is_heartbeat_like_signal_row(row):
                heartbeat_row_count += 1
                continue

            non_heartbeat_row_count += 1
            if latest_signal_epoch is None or ts_epoch >= latest_signal_epoch:
                latest_signal_epoch = ts_epoch
                latest_signal_ts = str(row.get("ts"))

        return {
            "session_id": session_id,
            "stdout_path": str(stdout_path),
            "stdout_mtime_epoch": stdout_epoch,
            "latest_any_epoch": latest_any_epoch,
            "latest_any_ts": latest_any_ts,
            "latest_signal_epoch": latest_signal_epoch,
            "latest_signal_ts": latest_signal_ts,
            "session_row_count": len(session_rows),
            "heartbeat_row_count": heartbeat_row_count,
            "non_heartbeat_row_count": non_heartbeat_row_count,
        }

    def wait_for_session_quiescence(
        self,
        session_id: str,
        *,
        timeout_sec: float = 180.0,
        stdout_idle_sec: float = 12.0,
        signal_idle_sec: float = 12.0,
        stable_polls: int = 3,
        interval_sec: float = 1.0,
        require_non_heartbeat_signal: bool = True,
    ) -> dict[str, Any]:
        """
        Wait until session activity appears finished by using two clocks:
        - last write to `sessions/<id>/stdout.log`
        - last meaningful timeline row for that session (excluding keepalive-like eBPF summaries)
        """
        deadline = time.time() + timeout_sec
        stable_hits = 0
        last_snapshot: dict[str, Any] | None = None

        while time.time() < deadline:
            now_epoch = time.time()
            snapshot = self._session_activity_snapshot(session_id)
            last_snapshot = snapshot

            stdout_epoch = snapshot["stdout_mtime_epoch"]
            signal_epoch = snapshot["latest_signal_epoch"]
            if signal_epoch is None and not require_non_heartbeat_signal:
                signal_epoch = snapshot["latest_any_epoch"]

            stdout_idle = float("inf") if stdout_epoch is None else max(0.0, now_epoch - float(stdout_epoch))
            signal_idle = float("inf") if signal_epoch is None else max(0.0, now_epoch - float(signal_epoch))

            has_required_signal = snapshot["non_heartbeat_row_count"] > 0 or (
                not require_non_heartbeat_signal and snapshot["session_row_count"] > 0
            )
            is_idle = stdout_idle >= stdout_idle_sec and signal_idle >= signal_idle_sec

            if has_required_signal and is_idle:
                stable_hits += 1
                if stable_hits >= stable_polls:
                    return {
                        **snapshot,
                        "stdout_idle_sec": stdout_idle,
                        "signal_idle_sec": signal_idle,
                        "stable_polls": stable_hits,
                    }
            else:
                stable_hits = 0

            time.sleep(interval_sec)

        raise AssertionError(
            "Timed out waiting for session quiescence. "
            f"session_id={session_id} timeout_sec={timeout_sec} "
            f"stdout_idle_sec={stdout_idle_sec} signal_idle_sec={signal_idle_sec} "
            f"require_non_heartbeat_signal={require_non_heartbeat_signal} "
            f"last_snapshot={last_snapshot}"
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

    def _tui_driver_logs_dir(self) -> Path:
        logs_dir = self.temp_root / "harness_tui_driver"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def _read_driver_log_tail(self, path: Path, *, max_chars: int = 4000) -> str:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) <= max_chars:
            return text
        return text[-max_chars:]

    def start_harness_tui_interactive(
        self,
        *,
        tui_name: str,
        tui_cmd: str | None = None,
    ) -> RunningTuiProcess:
        """
        Start harness TUI in the background and keep stdin open for interactive input.
        Uses `script -qec` to ensure `harness.py tui` receives a tty.
        """
        command = f"python3 /usr/local/bin/harness.py tui --tui-name {shlex.quote(tui_name)}"
        compose_cmd: list[str] = self._compose_command("exec", "-T")
        if tui_cmd is not None:
            compose_cmd.extend(["-e", f"HARNESS_TUI_CMD={tui_cmd}"])
        compose_cmd.extend(["harness", "script", "-qec", command, "/dev/null"])

        logs_dir = self._tui_driver_logs_dir()
        stdout_path = logs_dir / f"{tui_name}.stdout.log"
        stderr_path = logs_dir / f"{tui_name}.stderr.log"

        with stdout_path.open("wb") as driver_stdout, stderr_path.open("wb") as driver_stderr:
            proc = subprocess.Popen(
                compose_cmd,
                cwd=str(self.root_dir),
                env=self.env,
                stdin=subprocess.PIPE,
                stdout=driver_stdout,
                stderr=driver_stderr,
            )

        if proc.stdin is None:
            raise AssertionError("Failed to open stdin pipe for interactive TUI process.")

        return RunningTuiProcess(
            process=proc,
            command=tuple(compose_cmd),
            tui_name=tui_name,
            driver_stdout_path=stdout_path,
            driver_stderr_path=stderr_path,
        )

    def wait_for_session_id_for_tui_name(
        self,
        tui_name: str,
        *,
        timeout_sec: float = 60.0,
        interval_sec: float = 0.5,
    ) -> str:
        labels_dir = self.log_root / "labels" / "sessions"
        deadline = time.time() + timeout_sec
        last_matches: list[str] = []
        while time.time() < deadline:
            matches: list[str] = []
            if labels_dir.exists():
                for label_file in labels_dir.glob("*.json"):
                    try:
                        payload = json.loads(label_file.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if payload.get("name") == tui_name:
                        matches.append(label_file.stem)
            last_matches = sorted(set(matches))
            if len(last_matches) == 1:
                return last_matches[0]
            if len(last_matches) > 1:
                raise AssertionError(
                    f"Found multiple sessions for tui_name={tui_name}: {last_matches}"
                )
            time.sleep(interval_sec)
        raise AssertionError(
            f"Timed out waiting for session label for tui_name={tui_name}. "
            f"labels_dir={labels_dir} last_matches={last_matches}"
        )

    def send_tui_input(self, handle: RunningTuiProcess, text: str, *, newline: bool = True) -> None:
        # Harness TUI runs in raw mode; Enter must be carriage return, not newline.
        payload = text + ("\r" if newline else "")
        self.send_tui_bytes(handle, payload.encode("utf-8"))

    def send_tui_bytes(self, handle: RunningTuiProcess, payload: bytes) -> None:
        proc = handle.process
        if proc.poll() is not None:
            raise AssertionError(
                f"TUI process already exited for {handle.tui_name} "
                f"returncode={proc.returncode}\n"
                f"driver_stdout_tail:\n{self._read_driver_log_tail(handle.driver_stdout_path)}\n"
                f"driver_stderr_tail:\n{self._read_driver_log_tail(handle.driver_stderr_path)}"
            )
        assert proc.stdin is not None
        proc.stdin.write(payload)
        proc.stdin.flush()

    def prime_tui_terminal(
        self,
        handle: RunningTuiProcess,
        *,
        attempts: int = 20,
        interval_sec: float = 0.1,
    ) -> None:
        """
        Feed minimal terminal capability responses expected by full-screen TUIs
        when this test drives them through non-interactive pipes.
        """
        # Cursor position report + primary device attributes + fg/bg color query responses.
        payload = b"\x1b[15;1R\x1b[?1;2c\x1b]10;rgb:0000/0000/0000\x07\x1b]11;rgb:ffff/ffff/ffff\x07"
        for _ in range(max(1, attempts)):
            if handle.process.poll() is not None:
                return
            self.send_tui_bytes(handle, payload)
            if interval_sec > 0:
                time.sleep(interval_sec)

    def send_tui_ctrl_c(self, handle: RunningTuiProcess) -> None:
        proc = handle.process
        if proc.poll() is not None:
            return
        if proc.stdin is None or proc.stdin.closed:
            return
        try:
            proc.stdin.write(b"\x03")
            proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            return

    def stop_harness_tui_interactive(
        self,
        handle: RunningTuiProcess,
        *,
        wait_timeout_sec: float = 20.0,
    ) -> subprocess.CompletedProcess[str]:
        proc = handle.process

        if proc.poll() is None:
            self.send_tui_ctrl_c(handle)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self.send_tui_ctrl_c(handle)
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    if proc.stdin is not None and not proc.stdin.closed:
                        try:
                            proc.stdin.close()
                        except OSError:
                            pass
                    try:
                        proc.wait(timeout=wait_timeout_sec)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        try:
                            proc.wait(timeout=4.0)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=4.0)

        return subprocess.CompletedProcess(
            args=list(handle.command),
            returncode=proc.returncode if proc.returncode is not None else 1,
            stdout=self._read_driver_log_tail(handle.driver_stdout_path, max_chars=12000),
            stderr=self._read_driver_log_tail(handle.driver_stderr_path, max_chars=12000),
        )

    def host_log_path_from_container_path(self, container_path: str) -> Path:
        if not container_path.startswith("/logs/"):
            raise AssertionError(f"Unexpected container log path: {container_path}")
        return self.log_root / container_path.removeprefix("/logs/")
