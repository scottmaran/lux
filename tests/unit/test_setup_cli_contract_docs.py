from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_cli_contract_documents_setup_shims_and_safer_autostart() -> None:
    """CLI contract docs should describe setup shim step and optional safer auto-start behavior."""
    text = (ROOT_DIR / "docs" / "contracts" / "cli.md").read_text(
        encoding="utf-8", errors="replace"
    )

    assert "optional shim enablement" in text
    assert "optional safer auto-start" in text
    assert "provider plane is not auto-started" in text
    assert "lux setup --defaults" in text
