#!/usr/bin/env python3
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/x-asciinema", ".cast")


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
LABELS_DIR = LOG_ROOT / "labels"
SESSION_LABELS_DIR = LABELS_DIR / "sessions"
JOB_LABELS_DIR = LABELS_DIR / "jobs"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_valid_run_id(value: str) -> bool:
    return bool(RUN_ID_RE.fullmatch(value))


def load_label(path: Path) -> dict | None:
    data = read_json(path)
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    return {"name": name.strip(), "updated_at": data.get("updated_at")}


def write_label(dir_path: Path, run_id: str, name: str) -> dict:
    dir_path.mkdir(parents=True, exist_ok=True)
    payload = {"name": name, "updated_at": now_iso()}
    tmp_path = dir_path / f".{run_id}.json.tmp"
    final_path = dir_path / f"{run_id}.json"
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, final_path)
    return payload


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
        cast_path = entry / "tui.cast"
        if cast_path.exists():
            meta.setdefault("tui_cast_path", str(cast_path))
            meta.setdefault("tui_cast_format", "asciinema-v2")
            meta["tui_available"] = True
        else:
            meta["tui_available"] = False
        label = load_label(SESSION_LABELS_DIR / f"{session_id}.json")
        if label:
            meta["name"] = label["name"]
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
        label = load_label(JOB_LABELS_DIR / f"{job_id}.json")
        if label:
            payload["name"] = label["name"]
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

    def _bytes(self, payload: bytes, status: int = 200, content_type: str = "application/octet-stream") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, path: Path) -> None:
        content_type, _ = mimetypes.guess_type(path.name)
        payload = path.read_bytes()
        self._bytes(payload, 200, content_type or "application/octet-stream")

    def _resolve_static(self, request_path: str) -> Path | None:
        if request_path in ("/", "/index.html"):
            target = BUILD_DIR / "index.html"
            return target if target.exists() else None
        target = BUILD_DIR / request_path.lstrip("/")
        if target.exists() and target.is_file():
            return target
        return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            return self.handle_api(parsed)

        target = self._resolve_static(parsed.path)
        if target:
            return self._send_file(target)

        index_path = BUILD_DIR / "index.html"
        if index_path.exists():
            return self._send_file(index_path)
        return self._bytes(b"Not found", 404, "text/plain")

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        return self.handle_api_patch(parsed)

    def handle_api(self, parsed) -> None:
        if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/tui.cast"):
            run_id = parsed.path[len("/api/sessions/") : -len("/tui.cast")]
            return self._send_session_cast(run_id)
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

    def _send_session_cast(self, run_id: str) -> None:
        if not run_id or not is_valid_run_id(run_id):
            return self._json({"error": "invalid id"}, 400)
        cast_path = SESSIONS_DIR / run_id / "tui.cast"
        if not cast_path.exists():
            return self._json({"error": "not found"}, 404)
        return self._send_file(cast_path)

    def handle_api_patch(self, parsed) -> None:
        if parsed.path.startswith("/api/sessions/"):
            run_id = parsed.path[len("/api/sessions/") :]
            return self._handle_rename(run_id, SESSION_LABELS_DIR, SESSIONS_DIR)
        if parsed.path.startswith("/api/jobs/"):
            run_id = parsed.path[len("/api/jobs/") :]
            return self._handle_rename(run_id, JOB_LABELS_DIR, JOBS_DIR)
        return self._json({"error": "not found"}, 404)

    def _read_json_body(self) -> tuple[dict | None, str | None]:
        length_raw = self.headers.get("Content-Length", "0")
        try:
            length = int(length_raw)
        except ValueError:
            return None, "invalid content length"
        if length <= 0:
            return None, "invalid json"
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return None, "invalid json"
        if not isinstance(payload, dict):
            return None, "invalid json"
        return payload, None

    def _handle_rename(self, run_id: str, label_dir: Path, run_dir: Path) -> None:
        if not run_id or not is_valid_run_id(run_id):
            return self._json({"error": "invalid id"}, 400)
        if not (run_dir / run_id).exists():
            return self._json({"error": "not found"}, 404)

        payload, err = self._read_json_body()
        if err:
            return self._json({"error": err}, 400)

        name = payload.get("name")
        if not isinstance(name, str):
            return self._json({"error": "name is required"}, 400)
        name = name.strip()
        if not name:
            return self._json({"error": "name is required"}, 400)

        label = write_label(label_dir, run_id, name)
        return self._json({"id": run_id, "name": label["name"], "updated_at": label["updated_at"]})

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
