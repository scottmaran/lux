from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = FIXTURE_DIR / "schemas" / "case_schema.yaml"

AUDIT_FILTER_SCRIPT = ROOT_DIR / "collector" / "scripts" / "filter_audit_logs.py"
EBPF_FILTER_SCRIPT = ROOT_DIR / "collector" / "scripts" / "filter_ebpf_logs.py"
SUMMARY_SCRIPT = ROOT_DIR / "collector" / "scripts" / "summarize_ebpf_logs.py"
MERGE_SCRIPT = ROOT_DIR / "collector" / "scripts" / "merge_filtered_logs.py"

DEFAULT_AUDIT_CONFIG = ROOT_DIR / "collector" / "config" / "filtering.yaml"
DEFAULT_EBPF_FILTER_CONFIG = ROOT_DIR / "collector" / "config" / "ebpf_filtering.yaml"
DEFAULT_EBPF_SUMMARY_CONFIG = ROOT_DIR / "collector" / "config" / "ebpf_summary.yaml"
DEFAULT_MERGE_CONFIG = ROOT_DIR / "collector" / "config" / "merge_filtering.yaml"


@dataclass(frozen=True)
class FixtureCase:
    stage: str
    path: Path

    @property
    def case_id(self) -> str:
        return f"{self.stage}/{self.path.name}"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _deep_merge(target: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def load_case_schema() -> dict[str, Any]:
    return _load_yaml(SCHEMA_PATH)


def discover_cases(stage: str) -> list[FixtureCase]:
    stage_dir = FIXTURE_DIR / stage
    if not stage_dir.exists():
        return []
    return [FixtureCase(stage=stage, path=path) for path in sorted(stage_dir.glob("case_*")) if path.is_dir()]


def _validate_schema_files(case: FixtureCase, schema: dict[str, Any]) -> None:
    common = schema.get("common", {})
    stage_rules = schema.get("stages", {}).get(case.stage, {})
    required = set(common.get("required_files", [])) | set(stage_rules.get("required_files", []))
    optional = set(common.get("optional_entries", [])) | set(stage_rules.get("optional_entries", []))

    one_of_groups: list[list[str]] = common.get("one_of", []) + stage_rules.get("one_of", [])
    for group in one_of_groups:
        if not any((case.path / candidate).exists() for candidate in group):
            raise AssertionError(
                f"{case.case_id}: expected one of {group} to exist."
            )

    for required_name in sorted(required):
        if not (case.path / required_name).exists():
            raise AssertionError(f"{case.case_id}: missing required entry {required_name}")

    allowed_entries = required | optional
    for group in one_of_groups:
        allowed_entries.update(group)

    for entry in case.path.iterdir():
        if entry.name in allowed_entries:
            continue
        raise AssertionError(f"{case.case_id}: unexpected entry {entry.name}")


def validate_case_structure(case: FixtureCase) -> None:
    schema = load_case_schema()
    _validate_schema_files(case, schema)


def _run_script(script: Path, config: dict[str, Any], work_dir: Path) -> None:
    config_path = work_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "--config", str(config_path)],
        cwd=str(ROOT_DIR),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Script failed: {script}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _load_expected(case: FixtureCase) -> list[dict[str, Any]]:
    return _read_jsonl(case.path / "expected.jsonl")


def _copy_tree_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _stage_audit_filter(case: FixtureCase, work_dir: Path, overrides: dict[str, Any]) -> list[dict[str, Any]]:
    config = copy.deepcopy(_load_yaml(DEFAULT_AUDIT_CONFIG))
    _deep_merge(config, overrides)
    (work_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (work_dir / "jobs").mkdir(parents=True, exist_ok=True)
    _copy_tree_if_exists(case.path / "sessions", work_dir / "sessions")
    _copy_tree_if_exists(case.path / "jobs", work_dir / "jobs")

    audit_input = work_dir / "input.log"
    audit_input.write_text((case.path / "input.log").read_text(encoding="utf-8"), encoding="utf-8")
    output = work_dir / "actual.jsonl"
    config["input"] = {"audit_log": str(audit_input)}
    config["output"] = {"jsonl": str(output)}
    config["sessions_dir"] = str(work_dir / "sessions")
    config["jobs_dir"] = str(work_dir / "jobs")
    _run_script(AUDIT_FILTER_SCRIPT, config, work_dir)
    return _read_jsonl(output)


def _stage_ebpf_filter(case: FixtureCase, work_dir: Path, overrides: dict[str, Any]) -> list[dict[str, Any]]:
    config = copy.deepcopy(_load_yaml(DEFAULT_EBPF_FILTER_CONFIG))
    _deep_merge(config, overrides)
    (work_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (work_dir / "jobs").mkdir(parents=True, exist_ok=True)
    _copy_tree_if_exists(case.path / "sessions", work_dir / "sessions")
    _copy_tree_if_exists(case.path / "jobs", work_dir / "jobs")

    audit_input = work_dir / "input.log"
    if (case.path / "input.log").exists():
        audit_input.write_text((case.path / "input.log").read_text(encoding="utf-8"), encoding="utf-8")
    else:
        audit_input.write_text("", encoding="utf-8")
    ebpf_input = work_dir / "input.jsonl"
    ebpf_input.write_text((case.path / "input.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    output = work_dir / "actual.jsonl"
    config["input"] = {"audit_log": str(audit_input), "ebpf_log": str(ebpf_input)}
    config["output"] = {"jsonl": str(output)}
    config["sessions_dir"] = str(work_dir / "sessions")
    config["jobs_dir"] = str(work_dir / "jobs")
    _run_script(EBPF_FILTER_SCRIPT, config, work_dir)
    return _read_jsonl(output)


def _stage_summary(case: FixtureCase, work_dir: Path, overrides: dict[str, Any]) -> list[dict[str, Any]]:
    config = copy.deepcopy(_load_yaml(DEFAULT_EBPF_SUMMARY_CONFIG))
    _deep_merge(config, overrides)
    input_path = work_dir / "input.jsonl"
    input_path.write_text((case.path / "input.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    output = work_dir / "actual.jsonl"
    config["input"] = {"jsonl": str(input_path)}
    config["output"] = {"jsonl": str(output)}
    _run_script(SUMMARY_SCRIPT, config, work_dir)
    return _read_jsonl(output)


def _stage_merge(case: FixtureCase, work_dir: Path, overrides: dict[str, Any]) -> list[dict[str, Any]]:
    config = copy.deepcopy(_load_yaml(DEFAULT_MERGE_CONFIG))
    _deep_merge(config, overrides)
    audit_input = work_dir / "input.audit.jsonl"
    ebpf_input = work_dir / "input.ebpf.jsonl"
    audit_input.write_text((case.path / "input.audit.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    ebpf_input.write_text((case.path / "input.ebpf.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    output = work_dir / "actual.jsonl"
    config["inputs"] = [
        {"path": str(audit_input), "source": "audit"},
        {"path": str(ebpf_input), "source": "ebpf"},
    ]
    config["output"] = {"jsonl": str(output)}
    _run_script(MERGE_SCRIPT, config, work_dir)
    return _read_jsonl(output)


def _stage_pipeline(case: FixtureCase, work_dir: Path, overrides: dict[str, Any]) -> list[dict[str, Any]]:
    (work_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (work_dir / "jobs").mkdir(parents=True, exist_ok=True)
    _copy_tree_if_exists(case.path / "sessions", work_dir / "sessions")
    _copy_tree_if_exists(case.path / "jobs", work_dir / "jobs")

    audit_input = work_dir / "input.log"
    ebpf_input = work_dir / "input.jsonl"
    audit_input.write_text((case.path / "input.log").read_text(encoding="utf-8"), encoding="utf-8")
    ebpf_input.write_text((case.path / "input.jsonl").read_text(encoding="utf-8"), encoding="utf-8")

    audit_output = work_dir / "filtered_audit.jsonl"
    ebpf_output = work_dir / "filtered_ebpf.jsonl"
    summary_output = work_dir / "filtered_ebpf_summary.jsonl"
    timeline_output = work_dir / "actual.jsonl"

    audit_cfg = copy.deepcopy(_load_yaml(DEFAULT_AUDIT_CONFIG))
    _deep_merge(audit_cfg, overrides.get("audit_filter", {}))
    audit_cfg["input"] = {"audit_log": str(audit_input)}
    audit_cfg["output"] = {"jsonl": str(audit_output)}
    audit_cfg["sessions_dir"] = str(work_dir / "sessions")
    audit_cfg["jobs_dir"] = str(work_dir / "jobs")
    _run_script(AUDIT_FILTER_SCRIPT, audit_cfg, work_dir)

    ebpf_cfg = copy.deepcopy(_load_yaml(DEFAULT_EBPF_FILTER_CONFIG))
    _deep_merge(ebpf_cfg, overrides.get("ebpf_filter", {}))
    ebpf_cfg["input"] = {"audit_log": str(audit_input), "ebpf_log": str(ebpf_input)}
    ebpf_cfg["output"] = {"jsonl": str(ebpf_output)}
    ebpf_cfg["sessions_dir"] = str(work_dir / "sessions")
    ebpf_cfg["jobs_dir"] = str(work_dir / "jobs")
    _run_script(EBPF_FILTER_SCRIPT, ebpf_cfg, work_dir)

    summary_cfg = copy.deepcopy(_load_yaml(DEFAULT_EBPF_SUMMARY_CONFIG))
    _deep_merge(summary_cfg, overrides.get("summary", {}))
    summary_cfg["input"] = {"jsonl": str(ebpf_output)}
    summary_cfg["output"] = {"jsonl": str(summary_output)}
    _run_script(SUMMARY_SCRIPT, summary_cfg, work_dir)

    merge_cfg = copy.deepcopy(_load_yaml(DEFAULT_MERGE_CONFIG))
    _deep_merge(merge_cfg, overrides.get("merge", {}))
    merge_cfg["inputs"] = [
        {"path": str(audit_output), "source": "audit"},
        {"path": str(summary_output), "source": "ebpf"},
    ]
    merge_cfg["output"] = {"jsonl": str(timeline_output)}
    _run_script(MERGE_SCRIPT, merge_cfg, work_dir)

    return _read_jsonl(timeline_output)


STAGE_RUNNERS = {
    "audit_filter": _stage_audit_filter,
    "ebpf_filter": _stage_ebpf_filter,
    "summary": _stage_summary,
    "merge": _stage_merge,
    "pipeline": _stage_pipeline,
}


def run_case(case: FixtureCase, temp_dir: Path) -> list[dict[str, Any]]:
    overrides = _load_yaml(case.path / "config.yaml")
    runner = STAGE_RUNNERS[case.stage]
    return runner(case, temp_dir, overrides)


def assert_expected_rows(case: FixtureCase, actual_rows: list[dict[str, Any]]) -> None:
    expected_rows = _load_expected(case)
    if actual_rows != expected_rows:
        expected = json.dumps(expected_rows, indent=2, sort_keys=True)
        actual = json.dumps(actual_rows, indent=2, sort_keys=True)
        raise AssertionError(f"{case.case_id} mismatch.\nEXPECTED:\n{expected}\nACTUAL:\n{actual}")

