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


def test_installer_uses_fixed_layout_and_does_not_create_data_dirs(
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

        installer = _run(
            ["bash", str(ROOT_DIR / "install_lux.sh"), "--version", "v0.1.0"],
            cwd=ROOT_DIR,
            env=env,
            timeout=300,
        )
        assert "not on your PATH" in installer.stdout
        assert "$HOME/.local/bin" in installer.stdout
        assert "'lux' may be \"command not found\"" in installer.stdout
        assert "source ~/.zprofile" in installer.stdout
        assert "command not found" not in installer.stderr

        install_dir = home / ".lux"
        version_dir = install_dir / "versions" / "0.1.0"
        current_link = install_dir / "current"
        bin_link = home / ".local" / "bin" / "lux"
        config_path = home / ".config" / "lux" / "config.yaml"

        assert (version_dir / "lux").exists(), f"Expected lux binary under {version_dir}"
        assert (version_dir / "compose.yml").exists(), "Expected compose.yml in installed bundle."
        assert (version_dir / "config" / "default.yaml").exists(), "Expected default config in bundle."

        assert current_link.is_symlink(), "Expected ~/.lux/current symlink."
        assert bin_link.is_symlink(), "Expected ~/.local/bin/lux symlink."
        assert config_path.exists(), "Expected ~/.config/lux/config.yaml to be created."

        # Installer should not create log/workspace directories; config apply does that.
        assert not (home / "lux-logs").exists()
        assert not (home / "lux-workspace").exists()

        # The installed binary should work and resolve fixed install/bin paths under HOME.
        result = _run([str(bin_link), "--json", "paths"], cwd=ROOT_DIR, env=env, timeout=60)
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["result"]["install_dir"] == str(install_dir)
        assert payload["result"]["bin_dir"] == str(home / ".local" / "bin")


def test_installer_supports_local_bundle_and_checksum(
    tmp_path: Path,
    lux_cli_binary: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    server_root = tmp_path / "server"
    server_root.mkdir(parents=True, exist_ok=True)

    artifacts = build_fake_release_bundle(
        server_root=server_root,
        repo_root=ROOT_DIR,
        version="v0.1.0",
        lux_binary=lux_cli_binary,
    )
    bundle_path = Path(artifacts["bundle_path"])
    checksum_path = Path(artifacts["checksum_path"])

    env = os.environ.copy()
    env["HOME"] = str(home)

    installer = _run(
        [
            "bash",
            str(ROOT_DIR / "install_lux.sh"),
            "--version",
            "v0.1.0",
            "--bundle",
            str(bundle_path),
            "--checksum",
            str(checksum_path),
        ],
        cwd=ROOT_DIR,
        env=env,
        timeout=300,
    )
    assert "not on your PATH" in installer.stdout
    assert "$HOME/.local/bin" in installer.stdout
    assert "command not found" not in installer.stderr

    bin_link = home / ".local" / "bin" / "lux"
    assert bin_link.exists()

    result = _run([str(bin_link), "--json", "paths"], cwd=ROOT_DIR, env=env, timeout=60)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
