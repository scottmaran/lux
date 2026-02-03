#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sys
from urllib.parse import urlparse


def parse_timestamp(value: str) -> str | None:
    try:
        ts = float(value)
    except ValueError:
        return None
    iso = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat(timespec="milliseconds")
    if iso.endswith("+00:00"):
        iso = iso[:-6] + "Z"
    return iso


def parse_status(code_status: str) -> int | None:
    if "/" not in code_status:
        return None
    tail = code_status.split("/")[-1]
    if tail.isdigit():
        return int(tail)
    return None


def parse_host_port(method: str, url: str) -> tuple[str | None, int | None]:
    if not url or url == "-":
        return None, None
    if method.upper() == "CONNECT":
        if ":" in url:
            host, port = url.rsplit(":", 1)
            if port.isdigit():
                return host, int(port)
            return host, None
        return url, None
    parsed = urlparse(url)
    if parsed.hostname:
        port = parsed.port
        if port is None:
            if parsed.scheme == "https":
                port = 443
            elif parsed.scheme == "http":
                port = 80
        return parsed.hostname, port
    return None, None


def parse_line(line: str) -> dict | None:
    parts = line.split()
    if len(parts) < 7:
        return None

    ts = parse_timestamp(parts[0])
    if ts is None:
        return None

    elapsed_ms = int(parts[1]) if parts[1].isdigit() else None
    client_ip = parts[2]
    status = parse_status(parts[3])
    bytes_sent = int(parts[4]) if parts[4].isdigit() else None
    method = parts[5]
    url = parts[6]
    user = parts[7] if len(parts) > 7 else "-"

    host, port = parse_host_port(method, url)

    event: dict[str, object] = {
        "ts": ts,
        "source": "proxy",
        "event_type": "http",
        "method": method,
        "url": url,
    }

    if status is not None:
        event["status"] = status
    if host:
        event["host"] = host
    if port is not None:
        event["port"] = port
    if client_ip and client_ip != "-":
        event["client_ip"] = client_ip
    if elapsed_ms is not None:
        event["elapsed_ms"] = elapsed_ms
    if bytes_sent is not None:
        event["bytes"] = bytes_sent
    if user and user != "-":
        event["proxy_user"] = user
        if user.startswith("session_"):
            event["session_id"] = user
        elif user.startswith("job_"):
            event["job_id"] = user

    return event


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse squid access.log into JSONL proxy events.")
    parser.add_argument(
        "--output",
        default="/logs/filtered_proxy.jsonl",
        help="Path to JSONL output (append)",
    )
    args = parser.parse_args()

    try:
        output = open(args.output, "a", encoding="utf-8")
    except OSError as exc:
        print(f"proxy-parser: failed to open output {args.output}: {exc}", file=sys.stderr)
        return 1

    with output:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            event = parse_line(line)
            if event is None:
                continue
            output.write(json.dumps(event, separators=(",", ":")) + "\n")
            output.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
