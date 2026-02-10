from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, TypeVar


T = TypeVar("T")


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        is_last = idx == (len(lines) - 1)
        has_line_ending = raw_line.endswith("\n") or raw_line.endswith("\r")
        if is_last and not has_line_ending:
            # Ignore a possibly partial trailing append while live files are still being written.
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL row at {path}:{idx + 1}: {exc}") from exc
    return rows


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def wait_until(
    fn: Callable[[], T | None],
    *,
    timeout_sec: float,
    poll_sec: float = 0.25,
    description: str,
) -> T:
    deadline = time.monotonic() + timeout_sec
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = fn()
            if result is not None:
                return result
        except Exception as exc:  # pragma: no cover - used for diagnostics
            last_exc = exc
        time.sleep(poll_sec)
    if last_exc is not None:
        raise TimeoutError(f"timed out waiting for {description}: {last_exc}") from last_exc
    raise TimeoutError(f"timed out waiting for {description}")


def tail_text(path: Path, max_lines: int = 80) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])
