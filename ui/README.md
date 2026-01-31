# Zero-Build UI

This UI is plain HTML/CSS/JS served by a tiny Python HTTP server.

## Run locally (host)
```bash
python3 ui/server.py
```

Environment variables:
- `UI_BIND` (default: 0.0.0.0)
- `UI_PORT` (default: 8090)
- `UI_LOG_ROOT` (default: /logs, falls back to ./logs)

## API
See `UI_API.md` for the minimal API contract.
