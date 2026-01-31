#!/usr/bin/env python3
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
}


def detect_log_root() -> Path:
    env_path = os.getenv("UI_LOG_ROOT")
    if env_path:
        return Path(env_path)
    default = Path("/logs")
    if default.exists():
        return default
    return (ROOT.parent / "logs").resolve()


LOG_ROOT = detect_log_root()
TIMELINE_PATH = LOG_ROOT / "filtered_timeline.jsonl"
SESSIONS_DIR = LOG_ROOT / "sessions"
JOBS_DIR = LOG_ROOT / "jobs"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def normalize_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    value = ts.rstrip("Z")
    if "." in value:
        base, frac = value.split(".", 1)
        frac = (frac + "000000000")[:9]
    else:
        base = value
        frac = "000000000"
    return f"{base}.{frac}Z"


def parse_csv(values: list[str]) -> set[str]:
    if not values:
        return set()
    if len(values) == 1:
        parts = values[0].split(",")
    else:
        parts = values
    return {part.strip() for part in parts if part.strip()}


def load_sessions() -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for entry in SESSIONS_DIR.iterdir():
        if not entry.is_dir():
            continue
        meta_path = entry / "meta.json"
        meta = read_json(meta_path)
        if not meta:
            continue
        session_id = meta.get("session_id") or entry.name
        meta["session_id"] = session_id
        sessions.append(meta)
    sessions.sort(key=lambda item: str(item.get("started_at") or ""))
    return sessions


def load_jobs() -> list[dict]:
    if not JOBS_DIR.exists():
        return []
    jobs = []
    for entry in JOBS_DIR.iterdir():
        if not entry.is_dir():
            continue
        input_path = entry / "input.json"
        status_path = entry / "status.json"
        input_data = read_json(input_path) or {}
        status_data = read_json(status_path) or {}
        job_id = input_data.get("job_id") or status_data.get("job_id") or entry.name
        payload = {**input_data, **status_data}
        payload["job_id"] = job_id
        jobs.append(payload)
    jobs.sort(key=lambda item: str(item.get("started_at") or item.get("submitted_at") or ""))
    return jobs


def iter_timeline_rows(filters: dict) -> tuple[list[dict], dict]:
    start = normalize_ts(filters.get("start", [None])[0])
    end = normalize_ts(filters.get("end", [None])[0])
    limit_raw = filters.get("limit", [None])[0]
    limit = int(limit_raw) if limit_raw and limit_raw.isdigit() else None
    session_id = filters.get("session_id", [None])[0]
    job_id = filters.get("job_id", [None])[0]
    sources = parse_csv(filters.get("source", []))
    event_types = parse_csv(filters.get("event_type", []))

    rows = []
    counts: dict[str, int] = {}

    if not TIMELINE_PATH.exists():
        return rows, counts

    with TIMELINE_PATH.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = normalize_ts(event.get("ts"))
            if start and (ts is None or ts < start):
                continue
            if end and (ts is None or ts > end):
                continue
            if session_id and event.get("session_id") != session_id:
                continue
            if job_id and event.get("job_id") != job_id:
                continue
            if sources and event.get("source") not in sources:
                continue
            if event_types and event.get("event_type") not in event_types:
                continue
            rows.append(event)
            event_type = event.get("event_type") or "unknown"
            counts[event_type] = counts.get(event_type, 0) + 1
            if limit and len(rows) > limit:
                rows.pop(0)
    return rows, counts


class UIHandler(BaseHTTPRequestHandler):
    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, payload: str, status: int = 200, content_type: str = "text/plain") -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            return self.handle_api(parsed)
        if parsed.path in STATIC_FILES:
            target = ROOT / STATIC_FILES[parsed.path]
            if not target.exists():
                return self._text("Not found", 404)
            content = target.read_text(encoding="utf-8")
            if target.suffix == ".css":
                return self._text(content, 200, "text/css")
            if target.suffix == ".js":
                return self._text(content, 200, "text/javascript")
            return self._text(content, 200, "text/html")
        return self._text("Not found", 404)

    def handle_api(self, parsed) -> None:
        if parsed.path == "/api/sessions":
            return self._json({"sessions": load_sessions()})
        if parsed.path == "/api/jobs":
            return self._json({"jobs": load_jobs()})
        if parsed.path == "/api/timeline":
            filters = parse_qs(parsed.query)
            rows, _ = iter_timeline_rows(filters)
            return self._json({"rows": rows, "count": len(rows)})
        if parsed.path == "/api/summary":
            filters = parse_qs(parsed.query)
            _, counts = iter_timeline_rows(filters)
            total = sum(counts.values())
            return self._json({"counts": counts, "total": total})
        return self._json({"error": "not found"}, 404)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    bind = os.getenv("UI_BIND", "0.0.0.0")
    port = int(os.getenv("UI_PORT", "8090"))
    server = ThreadingHTTPServer((bind, port), UIHandler)
    print(f"ui server listening on {bind}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
