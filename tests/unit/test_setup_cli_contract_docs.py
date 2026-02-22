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


def test_cli_contract_documents_info_onboarding_tracks() -> None:
    """CLI contract docs should define the info command and both onboarding tracks."""
    text = (ROOT_DIR / "docs" / "contracts" / "cli.md").read_text(
        encoding="utf-8", errors="replace"
    )

    assert "### `info`" in text
    assert "manual provider plane + `lux tui`" in text
    assert "shim-enabled startup" in text
    assert "lux up --provider <provider> --wait" in text
    assert "<provider>" in text
