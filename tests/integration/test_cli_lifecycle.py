from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from tests.support.integration_stack import find_free_port, run_cmd


pytestmark = pytest.mark.integration

ROOT_DIR = Path(__file__).resolve().parents[2]
COMPOSE_BASE = ROOT_DIR / "compose.yml"
COMPOSE_TEST_OVERRIDE = ROOT_DIR / "tests" / "integration" / "compose.test.override.yml"


def _run_lasso(
    lasso_bin: Path,
    *,
    config_path: Path,
    compose_files: tuple[Path, ...],
    args: list[str],
    env: dict[str, str],
    timeout: float,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd: list[str] = [str(lasso_bin), "--json", "--config", str(config_path)]
    for compose_file in compose_files:
        cmd.extend(["--compose-file", str(compose_file)])
    cmd.extend(args)
    result = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            "lasso command failed.\n"
            f"cmd={' '.join(cmd)}\n"
            f"returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _write_cli_config(
    *,
    config_path: Path,
    log_root: Path,
    workspace_root: Path,
    project_name: str,
    api_port: int,
    api_token: str,
) -> None:
    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "paths:",
                f"  log_root: {log_root}",
                f"  workspace_root: {workspace_root}",
                "release:",
                '  tag: "local"',
                "docker:",
                f"  project_name: {project_name}",
                "harness:",
                "  api_host: 127.0.0.1",
                f"  api_port: {api_port}",
                f'  api_token: "{api_token}"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _cleanup_project(project_name: str) -> None:
    cmd: list[str] = ["docker", "compose", "-p", project_name, "-f", str(COMPOSE_BASE), "-f", str(COMPOSE_TEST_OVERRIDE)]
    cmd.extend(["down", "-v", "--remove-orphans"])
    run_cmd(cmd, cwd=ROOT_DIR, check=False, timeout=180)


def test_cli_up_wait_status_down_removes_volumes(
    tmp_path: Path,
    build_local_images,
    lasso_cli_binary: Path,
) -> None:
    runtime_root = tmp_path / f"cli-lifecycle-{uuid.uuid4().hex[:8]}"
    log_root = runtime_root / "logs"
    workspace_root = runtime_root / "workspace"
    config_dir = runtime_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.yaml"
    env_file = config_dir / "compose.env"
    project_name = f"lasso-cli-{uuid.uuid4().hex[:8]}"
    harness_port = find_free_port()
    api_token = f"token-{uuid.uuid4().hex}"
    compose_files = (COMPOSE_BASE, COMPOSE_TEST_OVERRIDE)

    _write_cli_config(
        config_path=config_path,
        log_root=log_root,
        workspace_root=workspace_root,
        project_name=project_name,
        api_port=harness_port,
        api_token=api_token,
    )

    env = os.environ.copy()
    env["LASSO_ENV_FILE"] = str(env_file)
    env["LASSO_BUNDLE_DIR"] = str(ROOT_DIR)
    env["HARNESS_HOST_PORT"] = str(harness_port)

    try:
        _run_lasso(
            lasso_cli_binary,
            config_path=config_path,
            compose_files=compose_files,
            args=["config", "apply"],
            env=env,
            timeout=120,
        )

        up = _run_lasso(
            lasso_cli_binary,
            config_path=config_path,
            compose_files=compose_files,
            args=["up", "--wait", "--timeout-sec", "240"],
            env=env,
            timeout=600,
        )
        payload = json.loads(up.stdout)
        assert payload["ok"] is True
        assert payload["result"].get("run_id"), f"Expected run_id in up payload: {payload}"

        status = _run_lasso(
            lasso_cli_binary,
            config_path=config_path,
            compose_files=compose_files,
            args=["status"],
            env=env,
            timeout=60,
        )
        payload = json.loads(status.stdout)
        assert payload["ok"] is True
        services = payload["result"]
        assert isinstance(services, list)
        assert services, f"Expected running services after up, got: {payload}"

        # Named volume should exist after up.
        volume_name = f"{project_name}_harness_keys"
        volume_ls = run_cmd(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            cwd=ROOT_DIR,
            check=True,
            timeout=30,
        )
        assert volume_name in (volume_ls.stdout or "").splitlines()

        _run_lasso(
            lasso_cli_binary,
            config_path=config_path,
            compose_files=compose_files,
            args=["down", "--volumes", "--remove-orphans"],
            env=env,
            timeout=240,
        )

        status = _run_lasso(
            lasso_cli_binary,
            config_path=config_path,
            compose_files=compose_files,
            args=["status"],
            env=env,
            timeout=60,
        )
        payload = json.loads(status.stdout)
        assert payload["ok"] is True
        assert payload["result"] == []

        # Volume should be removed by down --volumes.
        volume_ls = run_cmd(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            cwd=ROOT_DIR,
            check=True,
            timeout=30,
        )
        assert volume_name not in (volume_ls.stdout or "").splitlines()
    finally:
        _cleanup_project(project_name)
