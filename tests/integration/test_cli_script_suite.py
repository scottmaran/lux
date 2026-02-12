from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.support.integration_stack import run_cmd


pytestmark = pytest.mark.integration

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT_DIR / "scripts" / "cli_scripts"
COMPOSE_BASE = ROOT_DIR / "compose.yml"
COMPOSE_TEST_OVERRIDE = ROOT_DIR / "tests" / "integration" / "compose.test.override.yml"
COMPOSE_CLI_TUI_OVERRIDE = ROOT_DIR / "tests" / "integration" / "compose.cli.tui.override.yml"


@dataclass(frozen=True)
class CliScriptCase:
    name: str
    filename: str
    uses_docker: bool = False
    use_local_test_images: bool = False
    requires_pty: bool = False
    timeout_sec: float = 180.0
    allow_skip_output: bool = False

    @property
    def path(self) -> Path:
        return SCRIPT_DIR / self.filename


CLI_SCRIPT_CASES: tuple[CliScriptCase, ...] = (
    CliScriptCase("config-init", "00_config_init.sh"),
    CliScriptCase("config-validate-unknown", "01_config_validate_unknown.sh"),
    CliScriptCase("config-apply", "02_config_apply.sh"),
    CliScriptCase("config-apply-invalid", "03_config_apply_invalid.sh"),
    CliScriptCase("doctor-no-docker", "04_doctor_no_docker.sh"),
    CliScriptCase("doctor-log-root-unwritable", "05_doctor_log_root_unwritable.sh"),
    CliScriptCase("status-no-docker", "06_status_no_docker.sh"),
    CliScriptCase("upgrade-env", "11_upgrade_env.sh"),
    CliScriptCase(
        "missing-ghcr-auth",
        "12_missing_ghcr_auth.sh",
        uses_docker=True,
        timeout_sec=240.0,
        allow_skip_output=True,
    ),
    CliScriptCase(
        "up-wait-timeout",
        "13_up_wait_timeout.sh",
        uses_docker=True,
        use_local_test_images=True,
        timeout_sec=600.0,
    ),
    CliScriptCase(
        "down-cleanup-flags",
        "14_down_cleanup_flags.sh",
        uses_docker=True,
        use_local_test_images=True,
        timeout_sec=600.0,
    ),
    CliScriptCase("paths-json", "15_paths_json.sh"),
    CliScriptCase("uninstall-dry-run", "16_uninstall_dry_run.sh"),
    CliScriptCase(
        "uninstall-exec",
        "17_uninstall_exec.sh",
        uses_docker=True,
        use_local_test_images=True,
        timeout_sec=600.0,
    ),
    CliScriptCase("update-dry-run", "18_update_dry_run.sh"),
    CliScriptCase("update-rollback-dry-run", "19_update_rollback_dry_run.sh"),
    CliScriptCase(
        "stack-smoke",
        "10_stack_smoke.sh",
        uses_docker=True,
        use_local_test_images=True,
        requires_pty=True,
        timeout_sec=900.0,
    ),
)


def _write_compose_override_wrapper(wrapper_path: Path, lasso_binary_path: Path) -> None:
    content = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            (
                f'exec "{lasso_binary_path}" '
                f'--compose-file "{COMPOSE_BASE}" '
                f'--compose-file "{COMPOSE_TEST_OVERRIDE}" '
                f'--compose-file "{COMPOSE_CLI_TUI_OVERRIDE}" '
                '"$@"'
            ),
            "",
        ]
    )
    wrapper_path.write_text(content, encoding="utf-8")
    wrapper_path.chmod(0o755)


def _cleanup_project(project_name: str) -> None:
    compose_variants = (
        (COMPOSE_BASE,),
        (COMPOSE_BASE, COMPOSE_TEST_OVERRIDE),
        (COMPOSE_BASE, COMPOSE_TEST_OVERRIDE, COMPOSE_CLI_TUI_OVERRIDE),
    )
    for files in compose_variants:
        cmd: list[str] = ["docker", "compose", "-p", project_name]
        for compose_file in files:
            cmd.extend(["-f", str(compose_file)])
        cmd.extend(["down", "-v", "--remove-orphans"])
        run_cmd(cmd, cwd=ROOT_DIR, check=False, timeout=180)


def _run_cli_script(case: CliScriptCase, *, lasso_bin: Path, project_name: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "LASSO_BIN": str(lasso_bin),
            "LASSO_BUNDLE_DIR": str(ROOT_DIR),
            "LASSO_PROJECT_NAME": project_name,
        }
    )
    if case.use_local_test_images:
        env["LASSO_VERSION"] = "local"

    if case.requires_pty and shutil.which("script") is None:
        raise AssertionError(
            "script(1) is required to run CLI TUI smoke coverage but was not found in PATH."
        )

    cmd = [str(case.path)]
    if case.requires_pty:
        cmd = ["script", "-q", "/dev/null", str(case.path)]

    return subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=case.timeout_sec,
    )


@pytest.fixture(scope="session")
def lasso_cli_binary() -> Path:
    run_cmd(["cargo", "build", "--bin", "lasso"], cwd=ROOT_DIR / "lasso", timeout=1800)
    bin_path = ROOT_DIR / "lasso" / "target" / "debug" / "lasso"
    if not bin_path.exists():
        raise AssertionError(f"Built lasso binary is missing at {bin_path}")
    return bin_path


@pytest.fixture(scope="session")
def lasso_cli_compose_override_wrapper(
    tmp_path_factory: pytest.TempPathFactory,
    lasso_cli_binary: Path,
) -> Path:
    wrapper_dir = tmp_path_factory.mktemp("lasso-cli-wrapper")
    wrapper_path = wrapper_dir / "lasso-with-test-compose"
    _write_compose_override_wrapper(wrapper_path, lasso_cli_binary)
    return wrapper_path


@pytest.mark.parametrize("case", CLI_SCRIPT_CASES, ids=lambda c: c.name)
def test_cli_script_cases(
    case: CliScriptCase,
    request: pytest.FixtureRequest,
    lasso_cli_binary: Path,
    lasso_cli_compose_override_wrapper: Path,
) -> None:
    """Each shell CLI script succeeds under canonical pytest integration coverage."""
    if case.use_local_test_images:
        request.getfixturevalue("build_local_images")

    lasso_bin = lasso_cli_compose_override_wrapper if case.use_local_test_images else lasso_cli_binary
    project_name = f"lasso-test-cli-{case.name}-{uuid.uuid4().hex[:8]}"

    result: subprocess.CompletedProcess[str] | None = None
    try:
        result = _run_cli_script(case, lasso_bin=lasso_bin, project_name=project_name)
    finally:
        if case.uses_docker:
            _cleanup_project(project_name)

    assert result is not None
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    assert result.returncode == 0, (
        f"CLI script failed: {case.filename}\n"
        f"returncode={result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    if case.allow_skip_output:
        assert ("SKIP:" in output) or ("ok" in output), (
            f"Expected script to report explicit pass/skip marker: {case.filename}\n{output}"
        )
