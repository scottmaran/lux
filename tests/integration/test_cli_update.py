from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.support.fake_release import build_fake_release_bundle, serve_directory


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


def test_update_apply_and_rollback_against_local_release_server(
    tmp_path: Path,
    lux_cli_binary: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    server_root = tmp_path / "server"
    server_root.mkdir(parents=True, exist_ok=True)

    build_fake_release_bundle(
        server_root=server_root,
        repo_root=ROOT_DIR,
        version="v0.1.0",
        lux_binary=lux_cli_binary,
    )
    build_fake_release_bundle(
        server_root=server_root,
        repo_root=ROOT_DIR,
        version="v0.2.0",
        lux_binary=lux_cli_binary,
    )

    with serve_directory(server_root) as base_url:
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["LUX_RELEASE_BASE_URL"] = base_url

        _run(
            ["bash", str(ROOT_DIR / "install_lux.sh"), "--version", "v0.1.0"],
            cwd=ROOT_DIR,
            env=env,
            timeout=300,
        )

        lux = home / ".local" / "bin" / "lux"
        assert lux.exists(), "Expected installed lux binary symlink."

        update = _run(
            [str(lux), "--json", "update", "apply", "--to", "v0.2.0", "--yes"],
            cwd=ROOT_DIR,
            env=env,
            timeout=300,
        )
        payload = json.loads(update.stdout)
        assert payload["ok"] is True
        assert payload["result"]["action"] == "update_apply"
        assert payload["result"]["updated"] is True

        current_link = home / ".lux" / "current"
        assert current_link.is_symlink()
        assert current_link.resolve().name == "0.2.0"
        assert (home / ".lux" / "versions" / "0.2.0" / "lux").exists()

        rollback = _run(
            [str(lux), "--json", "update", "rollback", "--previous", "--yes"],
            cwd=ROOT_DIR,
            env=env,
            timeout=120,
        )
        payload = json.loads(rollback.stdout)
        assert payload["ok"] is True
        assert payload["result"]["action"] == "update_rollback"
        assert payload["result"]["updated"] is True
        assert current_link.resolve().name == "0.1.0"
