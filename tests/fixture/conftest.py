from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixture.schema_validation import FixtureCase, discover_case_dirs, validate_fixture_tree


FIXTURE_ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = FIXTURE_ROOT / "schemas" / "case_schema.yaml"


def _discover_cases() -> list[FixtureCase]:
    return discover_case_dirs(FIXTURE_ROOT)


def _format_schema_errors(errors: list[str]) -> str:
    header = ["fixture schema validation failed:"]
    header.extend(f"- {error}" for error in errors)
    return "\n".join(header)


@pytest.fixture(scope="session", autouse=True)
def enforce_fixture_schema() -> None:
    errors = validate_fixture_tree(FIXTURE_ROOT, SCHEMA_PATH)
    if errors:
        raise pytest.UsageError(_format_schema_errors(errors))


@pytest.fixture(scope="session")
def fixture_cases_by_category() -> dict[str, list[FixtureCase]]:
    grouped: dict[str, list[FixtureCase]] = {}
    for case in _discover_cases():
        grouped.setdefault(case.category, []).append(case)
    return grouped


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    return FIXTURE_ROOT
