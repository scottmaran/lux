from __future__ import annotations

import json
import os
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


def test_config_init_creates_and_preserves_existing(tmp_path: Path, lasso_cli_binary: Path) -> None:
    config_dir = tmp_path / "config"
    env = os.environ.copy()
    env["LASSO_CONFIG_DIR"] = str(config_dir)

    result = _run(
        [str(lasso_cli_binary), "--json", "config", "init"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["created"] is True

    config_path = config_dir / "config.yaml"
    assert config_path.exists()
    config_path.write_text("sentinel: true\n", encoding="utf-8")

    result = _run(
        [str(lasso_cli_binary), "--json", "config", "init"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["created"] is False
    assert config_path.read_text(encoding="utf-8") == "sentinel: true\n"


def test_config_validate_rejects_unknown_fields(tmp_path: Path, lasso_cli_binary: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "unknown_field: true",
                "paths:",
                f"  log_root: {tmp_path / 'logs'}",
                f"  workspace_root: {tmp_path / 'work'}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()

    result = _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "config", "validate"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "unknown" in (payload.get("error") or "").lower()


def test_config_apply_writes_env_file_and_creates_dirs(tmp_path: Path, lasso_cli_binary: Path) -> None:
    log_root = tmp_path / "logs"
    work_root = tmp_path / "work"
    env_file = tmp_path / "compose.env"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "paths:",
                f"  log_root: {log_root}",
                f"  workspace_root: {work_root}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["LASSO_ENV_FILE"] = str(env_file)

    _run(
        [str(lasso_cli_binary), "--config", str(config_path), "config", "apply"],
        cwd=ROOT_DIR,
        env=env,
        timeout=60,
    )

    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8", errors="replace")
    assert "LASSO_VERSION=" in content
    assert "LASSO_LOG_ROOT=" in content
    assert "LASSO_WORKSPACE_ROOT=" in content

    assert log_root.is_dir()
    assert work_root.is_dir()


def test_config_apply_invalid_config_is_actionable(tmp_path: Path, lasso_cli_binary: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("version: 1\nunknown: true\n", encoding="utf-8")
    env = os.environ.copy()

    result = _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "config", "apply"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    error = payload.get("error") or ""
    assert "config is invalid" in error
    assert "Please edit" in error


def test_doctor_reports_missing_docker_in_json(tmp_path: Path, lasso_cli_binary: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "paths:",
                f"  log_root: {tmp_path / 'logs'}",
                f"  workspace_root: {tmp_path / 'work'}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = ""

    result = _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "doctor"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "docker" in (payload.get("error") or "").lower()


def test_doctor_reports_log_root_unwritable_in_json(tmp_path: Path, lasso_cli_binary: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "paths:",
                "  log_root: /root/lasso-denied",
                f"  workspace_root: {tmp_path / 'work'}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()

    result = _run(
        [str(lasso_cli_binary), "--json", "--config", str(config_path), "doctor"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "log root" in (payload.get("error") or "").lower()


def test_status_fails_when_docker_missing(tmp_path: Path, lasso_cli_binary: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("version: 1\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = ""

    result = _run(
        [str(lasso_cli_binary), "--config", str(config_path), "status"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0


def test_config_apply_rewrites_env_file_when_release_tag_changes(
    tmp_path: Path,
    lasso_cli_binary: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    env_file = tmp_path / "compose.env"
    log_root = tmp_path / "logs"
    work_root = tmp_path / "work"

    env = os.environ.copy()
    env["LASSO_ENV_FILE"] = str(env_file)

    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "paths:",
                f"  log_root: {log_root}",
                f"  workspace_root: {work_root}",
                "release:",
                '  tag: "v0.1.0"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    _run(
        [str(lasso_cli_binary), "--config", str(config_path), "config", "apply"],
        cwd=ROOT_DIR,
        env=env,
        timeout=60,
    )
    assert "LASSO_VERSION=v0.1.0" in env_file.read_text(encoding="utf-8", errors="replace")

    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "paths:",
                f"  log_root: {log_root}",
                f"  workspace_root: {work_root}",
                "release:",
                '  tag: "v0.1.1"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    _run(
        [str(lasso_cli_binary), "--config", str(config_path), "config", "apply"],
        cwd=ROOT_DIR,
        env=env,
        timeout=60,
    )
    assert "LASSO_VERSION=v0.1.1" in env_file.read_text(encoding="utf-8", errors="replace")
