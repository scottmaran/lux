from __future__ import annotations

import pytest

from collector.tests.test_merge_filtered import MergeFilteredTests


pytestmark = pytest.mark.unit


class TestMergeFilteredBridge(MergeFilteredTests):
    """Collector merge unit behaviors remain covered under top-level pytest."""

