from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixture.helpers import SUMMARY_SCRIPT, expected_rows, load_case_config, run_script, write_yaml
from tests.support.io import read_jsonl


CASE_DIRS = sorted((Path(__file__).resolve().parent / "summary").glob("case_*"))


@pytest.mark.fixture
@pytest.mark.parametrize("case_dir", CASE_DIRS, ids=[path.name for path in CASE_DIRS])
def test_summary_fixture_cases(case_dir: Path, tmp_path: Path) -> None:
    """Summary fixture cases emit deterministic burst rows from filtered eBPF input."""
    input_path = tmp_path / "filtered_ebpf.jsonl"
    output_path = tmp_path / "filtered_ebpf_summary.jsonl"
    config_path = tmp_path / "config.yaml"

    input_path.write_text((case_dir / "input.jsonl").read_text(encoding="utf-8"), encoding="utf-8")

    config = load_case_config(case_dir)
    config["input"] = {"jsonl": str(input_path)}
    config["output"] = {"jsonl": str(output_path)}
    write_yaml(config_path, config)

    result = run_script(SUMMARY_SCRIPT, config_path)
    assert result.returncode == 0, result.stderr

    observed = read_jsonl(output_path)
    expected = expected_rows(case_dir)
    assert observed == expected, json.dumps({"observed": observed, "expected": expected}, indent=2)
