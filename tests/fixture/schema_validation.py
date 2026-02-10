from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class FixtureCase:
    category: str
    case_dir: Path


def load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    required_keys = {"required_files", "required_one_of", "optional_files"}
    missing = sorted(required_keys - payload.keys())
    if missing:
        raise ValueError(f"fixture schema missing keys: {missing}")
    return payload


def discover_case_dirs(fixture_root: Path) -> list[FixtureCase]:
    cases: list[FixtureCase] = []
    for category_dir in sorted(p for p in fixture_root.iterdir() if p.is_dir()):
        if category_dir.name in {"schemas", "__pycache__"}:
            continue
        for case_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            if case_dir.name.startswith("case_"):
                cases.append(FixtureCase(category=category_dir.name, case_dir=case_dir))
    return cases


def validate_case(case_dir: Path, schema: dict) -> list[str]:
    errors: list[str] = []
    files = sorted(p.name for p in case_dir.iterdir() if p.is_file())
    file_set = set(files)

    required_files = set(schema.get("required_files", []))
    for required in sorted(required_files):
        if required not in file_set:
            errors.append(f"missing required file '{required}'")

    for idx, group in enumerate(schema.get("required_one_of", []), start=1):
        if not any(item in file_set for item in group):
            errors.append(f"missing required one-of group {idx}: expected one of {group}")

    allowed = required_files | set(schema.get("optional_files", []))
    for group in schema.get("required_one_of", []):
        allowed.update(group)

    for filename in files:
        if filename not in allowed:
            errors.append(f"unexpected file '{filename}'")

    return errors


def validate_fixture_tree(fixture_root: Path, schema_path: Path) -> list[str]:
    schema = load_schema(schema_path)
    errors: list[str] = []
    cases = discover_case_dirs(fixture_root)
    if not cases:
        errors.append(f"no case_* directories discovered in {fixture_root}")
        return errors

    for case in cases:
        case_errors = validate_case(case.case_dir, schema)
        for error in case_errors:
            errors.append(f"{case.category}/{case.case_dir.name}: {error}")
    return errors
