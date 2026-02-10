from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixture.helpers import MERGE_SCRIPT, expected_rows, load_case_config, run_script, write_yaml
from tests.support.io import read_jsonl


CASE_DIRS = sorted((Path(__file__).resolve().parent / "merge").glob("case_*"))


@pytest.mark.fixture
@pytest.mark.parametrize("case_dir", CASE_DIRS, ids=[path.name for path in CASE_DIRS])
def test_merge_fixture_cases(case_dir: Path, tmp_path: Path) -> None:
    """Merge fixture cases normalize mixed sources into deterministic timeline rows."""
    audit_path = tmp_path / "filtered_audit.jsonl"
    ebpf_path = tmp_path / "filtered_ebpf_summary.jsonl"
    output_path = tmp_path / "filtered_timeline.jsonl"
    config_path = tmp_path / "config.yaml"

    audit_path.write_text((case_dir / "input_audit.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    ebpf_path.write_text((case_dir / "input_ebpf.jsonl").read_text(encoding="utf-8"), encoding="utf-8")

    config = load_case_config(case_dir)
    config["inputs"] = [
        {"path": str(audit_path), "source": "audit"},
        {"path": str(ebpf_path), "source": "ebpf"},
    ]
    config["output"] = {"jsonl": str(output_path)}
    write_yaml(config_path, config)

    result = run_script(MERGE_SCRIPT, config_path)
    assert result.returncode == 0, result.stderr

    observed = read_jsonl(output_path)
    expected = expected_rows(case_dir)
    assert observed == expected, json.dumps({"observed": observed, "expected": expected}, indent=2)
