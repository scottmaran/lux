from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from tests.support.io import read_jsonl


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_FILTER_SCRIPT = REPO_ROOT / "collector" / "scripts" / "filter_audit_logs.py"
EBPF_FILTER_SCRIPT = REPO_ROOT / "collector" / "scripts" / "filter_ebpf_logs.py"
SUMMARY_SCRIPT = REPO_ROOT / "collector" / "scripts" / "summarize_ebpf_logs.py"
MERGE_SCRIPT = REPO_ROOT / "collector" / "scripts" / "merge_filtered_logs.py"


def load_case_config(case_dir: Path) -> dict:
    with (case_dir / "config.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_json_array(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise AssertionError(f"expected JSON array at {path}")
    return payload


def write_metadata(case_dir: Path, sessions_dir: Path, jobs_dir: Path) -> None:
    sessions = load_json_array(case_dir / "sessions.json")
    jobs = load_json_array(case_dir / "jobs.json")

    sessions_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    for session in sessions:
        session_id = session.get("session_id")
        if not session_id:
            raise AssertionError(f"sessions.json entry missing session_id in {case_dir}")
        session_path = sessions_dir / str(session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        (session_path / "meta.json").write_text(json.dumps(session), encoding="utf-8")

    for job in jobs:
        job_id = job.get("job_id")
        if not job_id:
            raise AssertionError(f"jobs.json entry missing job_id in {case_dir}")
        job_path = jobs_dir / str(job_id)
        job_path.mkdir(parents=True, exist_ok=True)
        (job_path / "input.json").write_text(json.dumps(job), encoding="utf-8")
        status = job.get("status")
        if status:
            (job_path / "status.json").write_text(json.dumps(status), encoding="utf-8")


def run_script(script_path: Path, config_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path), "--config", str(config_path)],
        text=True,
        capture_output=True,
        check=False,
    )


def write_yaml(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def expected_rows(case_dir: Path) -> list[dict]:
    return read_jsonl(case_dir / "expected.jsonl")
