from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support.fake_release import detect_release_platform, normalize_version_tag


pytestmark = pytest.mark.external_install

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


def test_external_install_from_github_release_assets(tmp_path: Path) -> None:
    """
    Manual smoke test:
    - Download real release assets from GitHub using `gh release download`
    - Install from a local bundle into an isolated HOME

    Opt-in only:
      LUX_RUN_EXTERNAL_INSTALL=1
      LUX_EXTERNAL_INSTALL_VERSION=vX.Y.Z

    Optional:
      LUX_EXTERNAL_INSTALL_REPO=owner/repo (default: scottmaran/lux)
    """
    if os.environ.get("LUX_RUN_EXTERNAL_INSTALL") != "1":
        pytest.skip("Set LUX_RUN_EXTERNAL_INSTALL=1 to run this external install smoke test.")

    version = os.environ.get("LUX_EXTERNAL_INSTALL_VERSION")
    if not version:
        pytest.skip("Set LUX_EXTERNAL_INSTALL_VERSION=vX.Y.Z to run this external install smoke test.")

    repo = os.environ.get("LUX_EXTERNAL_INSTALL_REPO", "scottmaran/lux")
    if not repo.strip():
        pytest.skip("LUX_EXTERNAL_INSTALL_REPO is empty.")

    if shutil.which("gh") is None:
        pytest.skip("GitHub CLI is required for this test (missing `gh`).")

    version, version_tag = normalize_version_tag(version)
    os_name, arch = detect_release_platform()
    bundle_name = f"lux_{version_tag}_{os_name}_{arch}.tar.gz"
    checksum_name = f"{bundle_name}.sha256"

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    env_gh = os.environ.copy()
    env_gh.setdefault("GH_PROMPT_DISABLED", "1")

    pattern = f"{bundle_name}*"
    _run(
        [
            "gh",
            "release",
            "download",
            version,
            "-R",
            repo,
            "-p",
            pattern,
            "-D",
            str(download_dir),
        ],
        cwd=ROOT_DIR,
        env=env_gh,
        timeout=300,
    )

    bundle_path = download_dir / bundle_name
    checksum_path = download_dir / checksum_name
    assert bundle_path.exists(), f"Missing downloaded bundle at {bundle_path}"
    assert checksum_path.exists(), f"Missing downloaded checksum at {checksum_path}"

    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    env_install = os.environ.copy()
    env_install["HOME"] = str(home)

    _run(
        [
            "bash",
            str(ROOT_DIR / "install_lux.sh"),
            "--version",
            version,
            "--bundle",
            str(bundle_path),
            "--checksum",
            str(checksum_path),
        ],
        cwd=ROOT_DIR,
        env=env_install,
        timeout=300,
    )

    lux = home / ".local" / "bin" / "lux"
    assert lux.exists(), "Expected installed lux binary symlink."

    result = _run([str(lux), "--json", "paths"], cwd=ROOT_DIR, env=env_install, timeout=60)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["install_dir"] == str(home / ".lux")
    assert payload["result"]["bin_dir"] == str(home / ".local" / "bin")

    uninstall = _run(
        [
            str(lux),
            "--json",
            "uninstall",
            "--yes",
            "--remove-config",
            "--all-versions",
            "--force",
        ],
        cwd=ROOT_DIR,
        env=env_install,
        timeout=120,
    )
    payload = json.loads(uninstall.stdout)
    assert payload["ok"] is True
    assert payload["result"]["action"] == "uninstall"

    assert not (home / ".local" / "bin" / "lux").exists()
