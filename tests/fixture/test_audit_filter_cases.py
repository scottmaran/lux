from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixture.helpers import AUDIT_FILTER_SCRIPT, expected_rows, load_case_config, run_script, write_metadata, write_yaml
from tests.support.io import read_jsonl


CASE_DIRS = sorted((Path(__file__).resolve().parent / "audit_filter").glob("case_*"))


@pytest.mark.fixture
@pytest.mark.parametrize("case_dir", CASE_DIRS, ids=[path.name for path in CASE_DIRS])
def test_audit_filter_fixture_cases(case_dir: Path, tmp_path: Path) -> None:
    """Audit fixture cases produce deterministic output from canonical config + input."""
    audit_log = tmp_path / "audit.log"
    output_log = tmp_path / "filtered_audit.jsonl"
    sessions_dir = tmp_path / "sessions"
    jobs_dir = tmp_path / "jobs"
    config_path = tmp_path / "config.yaml"

    audit_log.write_text((case_dir / "input.log").read_text(encoding="utf-8"), encoding="utf-8")
    write_metadata(case_dir, sessions_dir, jobs_dir)

    config = load_case_config(case_dir)
    config["input"] = {"audit_log": str(audit_log)}
    config["output"] = {"jsonl": str(output_log)}
    config["sessions_dir"] = str(sessions_dir)
    config["jobs_dir"] = str(jobs_dir)
    write_yaml(config_path, config)

    result = run_script(AUDIT_FILTER_SCRIPT, config_path)
    assert result.returncode == 0, result.stderr

    observed = read_jsonl(output_log)
    expected = expected_rows(case_dir)
    assert observed == expected, json.dumps({"observed": observed, "expected": expected}, indent=2)
