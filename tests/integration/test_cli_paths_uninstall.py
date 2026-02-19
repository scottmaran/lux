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


def test_uninstall_remove_data_flag_is_rejected(tmp_path: Path, lux_cli_binary: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)

    result = _run(
        [str(lux_cli_binary), "uninstall", "--remove-data"],
        cwd=ROOT_DIR,
        env=env,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert "--remove-data" in combined


def test_uninstall_dry_run_preserves_files_and_never_targets_data_dirs(
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

        # Create sentinel data dirs that must never be removed by uninstall.
        (home / "lux-logs").mkdir(parents=True, exist_ok=True)
        (home / "lux-workspace").mkdir(parents=True, exist_ok=True)

        # Create env file so uninstall --remove-config has something to target.
        config_dir = home / ".config" / "lux"
        env_file = config_dir / "compose.env"
        env_file.write_text("LUX_VERSION=v0.1.0\n", encoding="utf-8")
        env["LUX_ENV_FILE"] = str(env_file)

        lux = home / ".local" / "bin" / "lux"
        result = _run(
            [
                str(lux),
                "--json",
                "uninstall",
                "--dry-run",
                "--remove-config",
                "--all-versions",
                "--force",
            ],
            cwd=ROOT_DIR,
            env=env,
            timeout=60,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["result"]["dry_run"] is True

        planned = payload["result"]["planned"]
        assert str(home / "lux-logs") not in planned
        assert str(home / "lux-workspace") not in planned

        # Dry run must not mutate filesystem.
        assert (home / ".lux" / "versions" / "0.1.0").exists()
        assert (home / ".lux" / "current").exists()
        assert lux.exists()
        assert (config_dir / "config.yaml").exists()
        assert env_file.exists()
        assert (home / "lux-logs").exists()
        assert (home / "lux-workspace").exists()


def test_uninstall_succeeds_with_invalid_config_and_without_env_file(
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

        # Data dirs must survive uninstall.
        (home / "lux-logs").mkdir(parents=True, exist_ok=True)
        (home / "lux-workspace").mkdir(parents=True, exist_ok=True)

        # Corrupt config so YAML parsing fails.
        config_dir = home / ".config" / "lux"
        config_path = config_dir / "config.yaml"
        config_path.write_text("version: 2\n: broken\n", encoding="utf-8")

        # Ensure env file is missing so uninstall skips stack shutdown without needing --force.
        env_file = config_dir / "compose.env"
        if env_file.exists():
            env_file.unlink()
        env["LUX_ENV_FILE"] = str(env_file)

        lux = home / ".local" / "bin" / "lux"
        result = _run(
            [
                str(lux),
                "--json",
                "uninstall",
                "--yes",
                "--remove-config",
                "--all-versions",
            ],
            cwd=ROOT_DIR,
            env=env,
            timeout=60,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["result"]["action"] == "uninstall"
        assert payload["result"]["dry_run"] is False
        assert any("env file missing" in warning for warning in payload["result"]["warnings"])

        assert not lux.exists()
        assert not (home / ".lux").exists() or not (home / ".lux" / "versions").exists()
        assert not config_path.exists()

        # Data directories should remain untouched.
        assert (home / "lux-logs").exists()
        assert (home / "lux-workspace").exists()
