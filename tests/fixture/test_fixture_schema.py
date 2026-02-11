from __future__ import annotations

import pytest

from .conftest import discover_cases, validate_case_structure


pytestmark = pytest.mark.fixture


def test_all_fixture_case_directories_match_schema() -> None:
    """Every fixture case directory follows the required stage schema."""
    stages = ["audit_filter", "ebpf_filter", "summary", "merge", "pipeline"]
    for stage in stages:
        cases = discover_cases(stage)
        assert cases, f"No fixture cases discovered for stage={stage}"
        for case in cases:
            validate_case_structure(case)

