#!/bin/sh
set -e

ROOT_DIR=${ROOT_DIR:-$HOME/lasso}
WORKSPACE=${WORKSPACE:-${ROOT_DIR}/workspace}
LOGS=${LOGS:-${ROOT_DIR}/logs}

mkdir -p "${WORKSPACE}" "${LOGS}"

# DNS + TCP egress

docker run --rm alpine sh -c "apk add --no-cache curl bind-tools >/dev/null; nslookup example.com >/dev/null; curl -I https://example.com >/dev/null"

# Unix domain socket connect

docker run --rm python:3-alpine sh -c "python - <<'PY'
import os, socket, threading, time
path = '/tmp/ipc.sock'
try:
    os.unlink(path)
except FileNotFoundError:
    pass

server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(path)
server.listen(1)

def accept():
    conn, _ = server.accept()
    conn.close()
    server.close()

t = threading.Thread(target=accept, daemon=True)
t.start()

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect(path)
client.close()
time.sleep(0.1)
PY"

echo "Generated DNS/TCP and unix socket activity. Check ${LOGS}/ebpf.jsonl."
