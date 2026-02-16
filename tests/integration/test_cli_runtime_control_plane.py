from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT_DIR = Path(__file__).resolve().parents[2]


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            "Command failed.\n"
            f"cmd={' '.join(cmd)}\n"
            f"returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _runtime_healthz(socket_path: Path) -> tuple[int, dict]:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(socket_path))
        request = (
            "GET /v1/healthz HTTP/1.1\r\n"
            "Host: lasso-runtime\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        sock.close()

    raw = b"".join(chunks)
    split = raw.find(b"\r\n\r\n")
    if split == -1:
        raise AssertionError("runtime healthz response missing header delimiter")
    headers = raw[:split].decode("utf-8", errors="replace").splitlines()
    status_line = headers[0] if headers else ""
    status_parts = status_line.split()
    if len(status_parts) < 2:
        raise AssertionError(f"invalid runtime status line: {status_line}")
    status_code = int(status_parts[1])
    body = raw[split + 4 :]
    payload = json.loads(body.decode("utf-8")) if body else {}
    return status_code, payload


def _write_minimal_config(config_path: Path, tmp_path: Path) -> None:
    config_path.write_text(
        "\n".join(
            [
                "version: 2",
                "paths:",
                f"  log_root: {tmp_path / 'logs'}",
                f"  workspace_root: {tmp_path / 'work'}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_runtime_up_status_down_exposes_healthz(tmp_path: Path, lasso_cli_binary: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_minimal_config(config_path, tmp_path)
    env = os.environ.copy()

    _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "runtime", "up"],
        cwd=ROOT_DIR,
        env=env,
        timeout=60,
    )
    status = _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "runtime", "status"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
    )
    payload = json.loads(status.stdout)
    assert payload["ok"] is True
    assert payload["result"]["running"] is True

    socket_path = Path(payload["result"]["socket_path"])
    code, health_payload = _runtime_healthz(socket_path)
    assert code == 200
    assert health_payload.get("ok") is True

    down = _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "runtime", "down"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
    )
    payload = json.loads(down.stdout)
    assert payload["ok"] is True
    assert payload["result"]["running"] is False


def test_runtime_auto_starts_for_routed_cli_command(
    tmp_path: Path,
    lasso_cli_binary: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    _write_minimal_config(config_path, tmp_path)
    env = os.environ.copy()

    _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "runtime", "down"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
        check=False,
    )

    run_result = _run(
        [
            str(lasso_cli_binary),
            "--json",
            "--config",
            str(config_path),
            "run",
            "--provider",
            "codex",
            "hello",
        ],
        cwd=ROOT_DIR,
        env=env,
        timeout=60,
        check=False,
    )
    assert run_result.returncode != 0
    run_payload = json.loads(run_result.stdout)
    assert run_payload["ok"] is False
    assert "provider plane" in (run_payload.get("error") or "").lower()

    status = _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "runtime", "status"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
    )
    payload = json.loads(status.stdout)
    assert payload["ok"] is True
    assert payload["result"]["running"] is True

    _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "runtime", "down"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
        check=False,
    )
