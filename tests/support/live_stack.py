from __future__ import annotations

import json
import os
import socket
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib import error, request

import yaml

from tests.support.io import read_json, read_jsonl, tail_text, wait_until


@dataclass
class StackConfig:
    run_cmd_template: str
    ownership_root_comm: list[str]
    include_codex_mount: bool = False
    lasso_version: str = "v0.1.4"
    api_token: str = "dev-token"


class LiveStack:
    def __init__(self, repo_root: Path, base_dir: Path, config: StackConfig):
        self.repo_root = repo_root
        self.base_dir = base_dir
        self.config = config
        self.project_name = f"lasso-test-{uuid.uuid4().hex[:10]}"
        self.harness_host_port = self._pick_free_port()
        self.log_root = base_dir / "logs"
        self.workspace_root = base_dir / "workspace"
        self.artifacts_root = base_dir / "artifacts"
        self.override_compose = base_dir / "compose.testing.override.yml"
        self.started = False

        self.log_root.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

        self._write_collector_configs()
        self._write_compose_override()

    @staticmethod
    def _pick_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @property
    def compose_files(self) -> list[Path]:
        files = [self.repo_root / "compose.yml", self.override_compose]
        if self.config.include_codex_mount:
            files.append(self.repo_root / "compose.codex.yml")
        return files

    @property
    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "LASSO_LOG_ROOT": str(self.log_root),
                "LASSO_WORKSPACE_ROOT": str(self.workspace_root),
                "LASSO_VERSION": self.config.lasso_version,
                "HARNESS_API_TOKEN": self.config.api_token,
                "HARNESS_RUN_CMD_TEMPLATE": self.config.run_cmd_template,
                "HARNESS_HOST_PORT": str(self.harness_host_port),
            }
        )
        return env

    def _write_yaml(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)

    def _write_collector_configs(self) -> None:
        cfg_dir = self.log_root / "testing"
        cfg_dir.mkdir(parents=True, exist_ok=True)

        filter_cfg = {
            "schema_version": "auditd.filtered.v1",
            "input": {"audit_log": "/logs/audit.log"},
            "sessions_dir": "/logs/sessions",
            "jobs_dir": "/logs/jobs",
            "output": {"jsonl": "/logs/filtered_audit.jsonl"},
            "grouping": {"strategy": "audit_seq"},
            "agent_ownership": {
                "uid": 1001,
                "root_comm": self.config.ownership_root_comm,
            },
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
            "linking": {
                "attach_cmd_to_fs": True,
                "attach_cmd_strategy": "last_exec_same_pid",
            },
        }

        ebpf_filter_cfg = {
            "schema_version": "ebpf.filtered.v1",
            "input": {
                "audit_log": "/logs/audit.log",
                "ebpf_log": "/logs/ebpf.jsonl",
            },
            "sessions_dir": "/logs/sessions",
            "jobs_dir": "/logs/jobs",
            "output": {"jsonl": "/logs/filtered_ebpf.jsonl"},
            "ownership": {
                "uid": 1001,
                "root_comm": self.config.ownership_root_comm,
                "pid_ttl_sec": 0,
                "exec_keys": ["exec"],
            },
            "exec": {
                "shell_comm": ["bash", "sh"],
                "shell_cmd_flag": "-lc",
            },
            "include": {
                "event_types": [
                    "net_connect",
                    "net_send",
                    "dns_query",
                    "dns_response",
                    "unix_connect",
                ]
            },
            "exclude": {
                "comm": ["initd", "dockerd", "chown"],
                "unix_paths": ["/var/run/nscd/socket", "/var/run/docker.raw.sock"],
                "net_dst_ports": [],
                "net_dst_ips": [],
            },
            "linking": {
                "attach_cmd_to_net": True,
                "attach_cmd_strategy": "last_exec_same_pid",
            },
            "pending_buffer": {
                "enabled": True,
                "ttl_sec": 1.5,
                "max_per_pid": 200,
                "max_total": 2000,
            },
        }

        summary_cfg = {
            "schema_version": "ebpf.summary.v1",
            "input": {"jsonl": "/logs/filtered_ebpf.jsonl"},
            "output": {"jsonl": "/logs/filtered_ebpf_summary.jsonl"},
            "burst_gap_sec": 5,
            "dns_lookback_sec": 2,
            "min_send_count": 0,
            "min_bytes_sent_total": 0,
        }

        merge_cfg = {
            "schema_version": "timeline.filtered.v1",
            "inputs": [
                {"path": "/logs/filtered_audit.jsonl", "source": "audit"},
                {"path": "/logs/filtered_ebpf_summary.jsonl", "source": "ebpf"},
            ],
            "output": {"jsonl": "/logs/filtered_timeline.jsonl"},
            "sorting": {"strategy": "ts_source_pid"},
        }

        self._write_yaml(cfg_dir / "filtering.yaml", filter_cfg)
        self._write_yaml(cfg_dir / "ebpf_filtering.yaml", ebpf_filter_cfg)
        self._write_yaml(cfg_dir / "ebpf_summary.yaml", summary_cfg)
        self._write_yaml(cfg_dir / "merge_filtering.yaml", merge_cfg)

    def _write_compose_override(self) -> None:
        override = {
            "services": {
                "collector": {
                    "environment": [
                        "COLLECTOR_FILTER_CONFIG=/logs/testing/filtering.yaml",
                        "COLLECTOR_EBPF_FILTER_CONFIG=/logs/testing/ebpf_filtering.yaml",
                        "COLLECTOR_EBPF_SUMMARY_CONFIG=/logs/testing/ebpf_summary.yaml",
                        "COLLECTOR_MERGE_FILTER_CONFIG=/logs/testing/merge_filtering.yaml",
                        "COLLECTOR_EBPF_SUMMARY_INTERVAL=1",
                        "COLLECTOR_MERGE_FILTER_INTERVAL=1",
                    ]
                },
                "harness": {
                    "environment": [
                        f"HARNESS_RUN_CMD_TEMPLATE={self.config.run_cmd_template}",
                    ]
                },
            }
        }
        self._write_yaml(self.override_compose, override)

    def compose_cmd(self, *args: str) -> list[str]:
        cmd = ["docker", "compose", "--project-name", self.project_name]
        for compose_file in self.compose_files:
            cmd.extend(["-f", str(compose_file)])
        cmd.extend(args)
        return cmd

    def run_compose(
        self,
        *args: str,
        capture_output: bool = False,
        check: bool = True,
        timeout_sec: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self.compose_cmd(*args),
            cwd=self.repo_root,
            env=self.env,
            check=check,
            text=True,
            capture_output=capture_output,
            timeout=timeout_sec,
        )

    def start(self) -> None:
        if self.started:
            return
        up_result = None
        for attempt in (1, 2, 3):
            up_result = self.run_compose(
                "up",
                "-d",
                "--build",
                "collector",
                "agent",
                "harness",
                capture_output=True,
                check=False,
            )
            if up_result.returncode != 0:
                stderr = up_result.stderr or ""
                transient = "No such container" in stderr
                if attempt < 3 and transient:
                    self.run_compose("down", "-v", capture_output=True, check=False)
                    continue
                break

            self.wait_for_harness_ready(timeout_sec=180)
            self.wait_for_file("filtered_timeline.jsonl", timeout_sec=120)
            if self._collector_healthy(timeout_sec=25):
                self.started = True
                return

            # collector auditd bootstrap can intermittently fail on host-pid mode; retry once.
            self.run_compose("down", "-v", capture_output=True, check=False)
            if attempt < 3:
                continue
            break

        raise RuntimeError(
            "docker compose up failed or collector was unhealthy:\n"
            f"stdout:\n{(up_result.stdout if up_result else '')}\n"
            f"stderr:\n{(up_result.stderr if up_result else '')}"
        )

    def _collector_healthy(self, timeout_sec: float) -> bool:
        audit_path = self.log_root / "audit.log"

        def _check() -> bool | None:
            if not audit_path.exists():
                return None
            text = audit_path.read_text(encoding="utf-8", errors="replace")
            if "type=SYSCALL" in text:
                return True
            return None

        try:
            wait_until(_check, timeout_sec=timeout_sec, poll_sec=0.5, description="collector audit syscall activity")
            return True
        except TimeoutError:
            return False

    def stop(self) -> None:
        logs_path = self.artifacts_root / "compose.log"
        try:
            logs = self.run_compose("logs", "--no-color", capture_output=True, check=False)
            logs_path.write_text(logs.stdout or logs.stderr, encoding="utf-8", errors="replace")
        except Exception:
            pass
        try:
            self.run_compose("down", "-v", check=False)
        finally:
            self.started = False

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        timeout_sec: float = 5.0,
    ) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.harness_host_port}{path}"
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            method=method,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Harness-Token": self.config.api_token,
            },
        )
        try:
            with request.urlopen(req, timeout=timeout_sec) as response:
                data = response.read().decode("utf-8")
                return response.getcode(), json.loads(data)
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return exc.code, payload

    def wait_for_harness_ready(self, timeout_sec: float = 60.0) -> None:
        def _check() -> bool | None:
            status, _payload = self._request("GET", "/jobs/_")
            if status in (200, 404):
                return True
            return None

        wait_until(_check, timeout_sec=timeout_sec, description="harness readiness")

    def submit_job(
        self,
        prompt: str,
        *,
        name: str | None = None,
        timeout_sec: int | None = None,
        capture_input: bool = True,
    ) -> dict:
        payload: dict = {
            "prompt": prompt,
            "capture_input": capture_input,
        }
        if name:
            payload["name"] = name
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        status, body = self._request("POST", "/run", payload)
        if status != 202:
            raise RuntimeError(f"/run returned {status}: {body}")
        return body

    def get_job(self, job_id: str) -> dict:
        status, body = self._request("GET", f"/jobs/{job_id}")
        if status != 200:
            raise RuntimeError(f"/jobs/{job_id} returned {status}: {body}")
        return body

    def wait_for_job(self, job_id: str, timeout_sec: float = 240.0) -> dict:
        def _check() -> dict | None:
            payload = self.get_job(job_id)
            if payload.get("status") in {"complete", "failed"}:
                return payload
            return None

        return wait_until(
            _check,
            timeout_sec=timeout_sec,
            poll_sec=1.0,
            description=f"job {job_id} completion",
        )

    def run_tui_command(
        self,
        command: str,
        *,
        name: str | None = None,
        timeout_sec: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        cmd = self.compose_cmd(
            "run",
            "--rm",
            "-e",
            "HARNESS_MODE=tui",
            "-e",
            f"HARNESS_TUI_CMD={command}",
        )
        if name:
            cmd.extend(["-e", f"HARNESS_TUI_NAME={name}"])
        cmd.append("harness")
        wrapped = ["script", "-q", "/dev/null", *cmd]
        return subprocess.run(
            wrapped,
            cwd=self.repo_root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )

    def wait_for_file(self, filename: str, timeout_sec: float = 60.0) -> Path:
        target = self.log_root / filename

        def _check() -> Path | None:
            if target.exists():
                return target
            return None

        return wait_until(_check, timeout_sec=timeout_sec, description=f"file {filename}")

    def read_jsonl(self, filename: str) -> list[dict]:
        return read_jsonl(self.log_root / filename)

    def read_job_input(self, job_id: str) -> dict:
        return read_json(self.log_root / "jobs" / job_id / "input.json")

    def read_job_status_file(self, job_id: str) -> dict:
        return read_json(self.log_root / "jobs" / job_id / "status.json")

    def wait_for_row(
        self,
        filename: str,
        predicate: Callable[[dict], bool],
        *,
        timeout_sec: float = 90.0,
    ) -> dict:
        def _check() -> dict | None:
            for row in self.read_jsonl(filename):
                if predicate(row):
                    return row
            return None

        return wait_until(
            _check,
            timeout_sec=timeout_sec,
            poll_sec=0.5,
            description=f"row in {filename}",
        )

    def all_sessions(self) -> list[Path]:
        session_root = self.log_root / "sessions"
        if not session_root.exists():
            return []
        return sorted([p for p in session_root.iterdir() if p.is_dir()], key=lambda p: p.name)

    def latest_session(self) -> Path | None:
        sessions = self.all_sessions()
        if not sessions:
            return None
        return sessions[-1]

    def session_meta(self, session_path: Path) -> dict:
        return read_json(session_path / "meta.json")

    def jobs_metadata(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        jobs_root = self.log_root / "jobs"
        if not jobs_root.exists():
            return result
        for path in jobs_root.iterdir():
            if not path.is_dir():
                continue
            input_meta = {}
            status_meta = {}
            input_path = path / "input.json"
            status_path = path / "status.json"
            if input_path.exists():
                input_meta = read_json(input_path)
            if status_path.exists():
                status_meta = read_json(status_path)
            combined = {}
            combined.update(input_meta)
            combined.update(status_meta)
            result[path.name] = combined
        return result

    def sessions_metadata(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for session_path in self.all_sessions():
            meta_path = session_path / "meta.json"
            if meta_path.exists():
                meta = read_json(meta_path)
                session_id = meta.get("session_id") or session_path.name
                result[session_id] = meta
        return result

    def compose_ps(self) -> list[dict]:
        result = self.run_compose("ps", "--format", "json", capture_output=True, check=False)
        text = (result.stdout or "").strip()
        if not text:
            return []
        if text.startswith("["):
            loaded = json.loads(text)
            if isinstance(loaded, list):
                return loaded
            return []
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    def assert_core_services_running(self) -> None:
        services = {row.get("Service"): row.get("State") for row in self.compose_ps()}
        for service in ("collector", "agent", "harness"):
            state = services.get(service, "")
            if "running" not in str(state).lower():
                raise AssertionError(f"service {service} not running: {services}")

    def diagnostics(self) -> str:
        lines = [
            f"project={self.project_name}",
            f"log_root={self.log_root}",
            f"artifacts={self.artifacts_root}",
            "timeline_tail:",
            tail_text(self.log_root / "filtered_timeline.jsonl", max_lines=40),
            "audit_tail:",
            tail_text(self.log_root / "filtered_audit.jsonl", max_lines=40),
            "ebpf_tail:",
            tail_text(self.log_root / "filtered_ebpf.jsonl", max_lines=40),
        ]
        return "\n".join(lines)
