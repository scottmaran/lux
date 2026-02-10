from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixture.helpers import (
    AUDIT_FILTER_SCRIPT,
    EBPF_FILTER_SCRIPT,
    MERGE_SCRIPT,
    SUMMARY_SCRIPT,
    expected_rows,
    load_case_config,
    run_script,
    write_metadata,
    write_yaml,
)
from tests.support.io import read_jsonl


CASE_DIRS = sorted((Path(__file__).resolve().parent / "pipeline").glob("case_*"))


@pytest.mark.fixture
@pytest.mark.parametrize("case_dir", CASE_DIRS, ids=[path.name for path in CASE_DIRS])
def test_pipeline_fixture_cases(case_dir: Path, tmp_path: Path) -> None:
    """Pipeline fixture cases validate filter -> summary -> merge contract as one flow."""
    input_audit = tmp_path / "audit.log"
    input_ebpf = tmp_path / "ebpf.jsonl"
    filtered_audit = tmp_path / "filtered_audit.jsonl"
    filtered_ebpf = tmp_path / "filtered_ebpf.jsonl"
    filtered_summary = tmp_path / "filtered_ebpf_summary.jsonl"
    timeline = tmp_path / "filtered_timeline.jsonl"
    sessions_dir = tmp_path / "sessions"
    jobs_dir = tmp_path / "jobs"

    input_audit.write_text((case_dir / "input.log").read_text(encoding="utf-8"), encoding="utf-8")
    input_ebpf.write_text((case_dir / "input.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    write_metadata(case_dir, sessions_dir, jobs_dir)

    config = load_case_config(case_dir)

    audit_cfg = dict(config["audit_filter"])
    audit_cfg["input"] = {"audit_log": str(input_audit)}
    audit_cfg["output"] = {"jsonl": str(filtered_audit)}
    audit_cfg["sessions_dir"] = str(sessions_dir)
    audit_cfg["jobs_dir"] = str(jobs_dir)
    audit_cfg_path = tmp_path / "audit_cfg.yaml"
    write_yaml(audit_cfg_path, audit_cfg)

    ebpf_cfg = dict(config["ebpf_filter"])
    ebpf_cfg["input"] = {"audit_log": str(input_audit), "ebpf_log": str(input_ebpf)}
    ebpf_cfg["output"] = {"jsonl": str(filtered_ebpf)}
    ebpf_cfg["sessions_dir"] = str(sessions_dir)
    ebpf_cfg["jobs_dir"] = str(jobs_dir)
    ebpf_cfg_path = tmp_path / "ebpf_cfg.yaml"
    write_yaml(ebpf_cfg_path, ebpf_cfg)

    summary_cfg = dict(config["summary"])
    summary_cfg["input"] = {"jsonl": str(filtered_ebpf)}
    summary_cfg["output"] = {"jsonl": str(filtered_summary)}
    summary_cfg_path = tmp_path / "summary_cfg.yaml"
    write_yaml(summary_cfg_path, summary_cfg)

    merge_cfg = dict(config["merge"])
    merge_cfg["inputs"] = [
        {"path": str(filtered_audit), "source": "audit"},
        {"path": str(filtered_summary), "source": "ebpf"},
    ]
    merge_cfg["output"] = {"jsonl": str(timeline)}
    merge_cfg_path = tmp_path / "merge_cfg.yaml"
    write_yaml(merge_cfg_path, merge_cfg)

    audit_result = run_script(AUDIT_FILTER_SCRIPT, audit_cfg_path)
    assert audit_result.returncode == 0, audit_result.stderr

    ebpf_result = run_script(EBPF_FILTER_SCRIPT, ebpf_cfg_path)
    assert ebpf_result.returncode == 0, ebpf_result.stderr

    summary_result = run_script(SUMMARY_SCRIPT, summary_cfg_path)
    assert summary_result.returncode == 0, summary_result.stderr

    merge_result = run_script(MERGE_SCRIPT, merge_cfg_path)
    assert merge_result.returncode == 0, merge_result.stderr

    observed = read_jsonl(timeline)
    expected = expected_rows(case_dir)
    assert observed == expected, json.dumps({"observed": observed, "expected": expected}, indent=2)
