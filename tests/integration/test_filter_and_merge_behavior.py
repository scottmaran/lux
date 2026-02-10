from __future__ import annotations

import uuid

import pytest

from tests.support.synthetic_logs import build_job_fs_sequence, make_net_send_event


pytestmark = pytest.mark.integration


def _details_path(row: dict) -> str | None:
    details = row.get("details") or {}
    return details.get("path")


def test_filter_and_merge_produce_audit_and_ebpf_rows(
    integration_stack,
    timeline_validator,
) -> None:
    """Collector filters + merge produce job-owned audit and eBPF timeline rows."""
    target_path = f"/work/filter_merge_{uuid.uuid4().hex[:8]}.txt"
    job_id, status = integration_stack.submit_and_wait(f"sleep 1; printf data > {target_path}")
    assert status["status"] == "complete"

    job_dir = integration_stack.log_root / "jobs" / job_id
    input_meta = integration_stack.read_json(job_dir / "input.json")
    root_pid = input_meta.get("root_pid")
    assert isinstance(root_pid, int), "Expected integer root_pid in job input metadata."
    child_pid = root_pid * 1000 + 1
    audit_lines = build_job_fs_sequence(
        root_pid=root_pid,
        child_pid=child_pid,
        target_path=target_path,
        seq_start=100,
        ts_root="1769030400.100",
        ts_child="1769030400.120",
        ts_fs="1769030400.200",
    )
    pipeline = integration_stack.run_collector_pipeline(
        audit_lines=audit_lines,
        ebpf_events=[make_net_send_event(pid=child_pid, ppid=root_pid, bytes_sent=17)],
    )
    rows = pipeline["timeline"]

    sources = {row.get("source") for row in rows}
    assert "audit" in sources
    assert "ebpf" in sources
    assert any(_details_path(row) == target_path and row.get("job_id") == job_id for row in rows)
    assert any(
        row.get("source") == "ebpf"
        and row.get("event_type") == "net_summary"
        and row.get("job_id") == job_id
        for row in rows
    )
    timeline_validator(
        log_root=integration_stack.log_root,
        timeline_path=integration_stack.log_root / "filtered_timeline.synthetic.jsonl",
    )
