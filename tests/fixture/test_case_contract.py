from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixture.schema_validation import discover_case_dirs


@pytest.mark.fixture
def test_fixture_directories_have_discoverable_cases(fixture_root: Path) -> None:
    """Fixture categories contain at least one discoverable `case_*` directory."""
    discovered = discover_case_dirs(fixture_root)
    categories = {case.category for case in discovered}
    expected = {"audit_filter", "ebpf_filter", "summary", "merge", "pipeline"}
    assert categories == expected
