from __future__ import annotations

import functools
import hashlib
import os
import platform
import shutil
import tarfile
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Iterator


def normalize_version_tag(version: str) -> tuple[str, str]:
    normalized = version.strip()
    if not normalized:
        raise ValueError("version is empty")
    if not normalized.startswith("v"):
        normalized = f"v{normalized}"
    return normalized, normalized[1:]


def detect_release_platform() -> tuple[str, str]:
    sysname = platform.system().lower()
    if sysname == "darwin":
        os_name = "darwin"
    elif sysname == "linux":
        os_name = "linux"
    else:
        raise RuntimeError(f"Unsupported platform for fake release bundle: {platform.system()}")

    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        arch = "amd64"
    elif machine in {"arm64", "aarch64"}:
        arch = "arm64"
    else:
        raise RuntimeError(f"Unsupported architecture for fake release bundle: {platform.machine()}")

    return os_name, arch


def sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_fake_release_bundle(
    *,
    server_root: Path,
    repo_root: Path,
    version: str,
    lux_binary: Path,
) -> dict[str, Path | str]:
    """
    Create a fake GitHub-release-like bundle under:
      server_root/<version>/lux_<ver>_<os>_<arch>.tar.gz (+ .sha256)

    The tarball contains a top-level directory exactly like the release workflow:
      lux_<ver>_<os>_<arch>/...
    """
    version, version_tag = normalize_version_tag(version)
    os_name, arch = detect_release_platform()

    bundle_dir_name = f"lux_{version_tag}_{os_name}_{arch}"
    bundle_name = f"{bundle_dir_name}.tar.gz"
    checksum_name = f"{bundle_name}.sha256"

    version_dir = server_root / version
    dist_dir = version_dir / "_dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    staging_dir = dist_dir / bundle_dir_name
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    (staging_dir / "config").mkdir(parents=True, exist_ok=True)

    shutil.copy2(lux_binary, staging_dir / "lux")
    # Ensure the copied binary is executable even if the underlying FS drops mode bits.
    os.chmod(staging_dir / "lux", 0o755)

    for compose in ("compose.yml", "compose.ui.yml"):
        shutil.copy2(repo_root / compose, staging_dir / compose)

    shutil.copy2(repo_root / "lux" / "config" / "default.yaml", staging_dir / "config" / "default.yaml")

    # Optional but keeps artifacts closer to the real release workflow.
    (staging_dir / "VERSION").write_text(f"{version_tag}\n", encoding="utf-8")
    shutil.copy2(repo_root / "README.md", staging_dir / "README.md")

    bundle_path = version_dir / bundle_name
    with tarfile.open(bundle_path, "w:gz") as tf:
        tf.add(staging_dir, arcname=bundle_dir_name)

    checksum_path = version_dir / checksum_name
    digest = sha256_hex(bundle_path)
    checksum_path.write_text(f"{digest}  {bundle_name}\n", encoding="utf-8")

    return {
        "version": version,
        "version_tag": version_tag,
        "os": os_name,
        "arch": arch,
        "bundle_name": bundle_name,
        "checksum_name": checksum_name,
        "bundle_path": bundle_path,
        "checksum_path": checksum_path,
    }


@contextmanager
def serve_directory(root: Path) -> Iterator[str]:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = int(httpd.server_address[1])
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
