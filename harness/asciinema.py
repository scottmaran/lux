import json
from typing import TextIO


def build_header(
    width: int,
    height: int,
    timestamp: int,
    command: str | None = None,
    title: str | None = None,
    env: dict | None = None,
) -> dict:
    header = {
        "version": 2,
        "width": int(width),
        "height": int(height),
        "timestamp": int(timestamp),
    }
    if command:
        header["command"] = command
    if title:
        header["title"] = title
    if env:
        header["env"] = env
    return header


def decode_bytes(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace")


def format_event(offset_seconds: float, stream: str, data: str) -> str:
    entry = [round(float(offset_seconds), 6), stream, data]
    return json.dumps(entry, ensure_ascii=False)


def write_header(handle: TextIO, header: dict) -> None:
    handle.write(json.dumps(header, ensure_ascii=False))
    handle.write("\n")
    handle.flush()


def write_event(handle: TextIO, offset_seconds: float, stream: str, data: str) -> None:
    handle.write(format_event(offset_seconds, stream, data))
    handle.write("\n")
    handle.flush()
