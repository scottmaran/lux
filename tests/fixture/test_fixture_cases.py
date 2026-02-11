from __future__ import annotations

import pytest

from .conftest import assert_expected_rows, discover_cases, run_case, validate_case_structure


pytestmark = pytest.mark.fixture


@pytest.mark.parametrize("case", discover_cases("audit_filter"), ids=lambda case: case.case_id)
def test_audit_filter_cases(case, tmp_path) -> None:
    """Audit filter cases produce exactly the expected output rows."""
    validate_case_structure(case)
    actual_rows = run_case(case, tmp_path)
    assert_expected_rows(case, actual_rows)


@pytest.mark.parametrize("case", discover_cases("ebpf_filter"), ids=lambda case: case.case_id)
def test_ebpf_filter_cases(case, tmp_path) -> None:
    """eBPF filter cases produce exactly the expected output rows."""
    validate_case_structure(case)
    actual_rows = run_case(case, tmp_path)
    assert_expected_rows(case, actual_rows)


@pytest.mark.parametrize("case", discover_cases("summary"), ids=lambda case: case.case_id)
def test_ebpf_summary_cases(case, tmp_path) -> None:
    """eBPF summary cases produce exactly the expected output rows."""
    validate_case_structure(case)
    actual_rows = run_case(case, tmp_path)
    assert_expected_rows(case, actual_rows)


@pytest.mark.parametrize("case", discover_cases("merge"), ids=lambda case: case.case_id)
def test_merge_cases(case, tmp_path) -> None:
    """Merge cases produce exactly the expected output rows."""
    validate_case_structure(case)
    actual_rows = run_case(case, tmp_path)
    assert_expected_rows(case, actual_rows)


@pytest.mark.parametrize("case", discover_cases("pipeline"), ids=lambda case: case.case_id)
def test_pipeline_cases(case, tmp_path) -> None:
    """Pipeline cases produce exactly the expected output rows."""
    validate_case_structure(case)
    actual_rows = run_case(case, tmp_path)
    assert_expected_rows(case, actual_rows)

