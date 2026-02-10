from __future__ import annotations

import pytest

from tests.support.io import read_jsonl


@pytest.mark.unit
def test_read_jsonl_ignores_partial_trailing_line(tmp_path) -> None:
    """Live JSONL tail reads should ignore an incomplete trailing append."""
    path = tmp_path / "timeline.jsonl"
    path.write_text('{"ok":1}\n{"partial":"x', encoding="utf-8")
    assert read_jsonl(path) == [{"ok": 1}]


@pytest.mark.unit
def test_read_jsonl_rejects_invalid_complete_line(tmp_path) -> None:
    """Invalid fully written JSONL rows should fail loudly for diagnostics."""
    path = tmp_path / "timeline.jsonl"
    path.write_text('{"ok":1}\n{"broken":}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSONL row"):
        read_jsonl(path)
