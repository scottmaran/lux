#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import selectors
import shlex
import signal
import subprocess
import sys
import termios
import threading
import time
import tty
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG_DIR = os.getenv("HARNESS_LOG_DIR", "/logs")
JOB_DIR = os.path.join(LOG_DIR, "jobs")
SESSION_DIR = os.path.join(LOG_DIR, "sessions")

AGENT_HOST = os.getenv("HARNESS_AGENT_HOST", "agent")
AGENT_PORT = int(os.getenv("HARNESS_AGENT_PORT", "22"))
AGENT_USER = os.getenv("HARNESS_AGENT_USER", "agent")
SSH_KEY_PATH = os.getenv("HARNESS_SSH_KEY_PATH", "/harness/keys/ssh_key")
SSH_KNOWN_HOSTS = os.getenv("HARNESS_SSH_KNOWN_HOSTS", "/harness/keys/known_hosts")

HTTP_BIND = os.getenv("HARNESS_HTTP_BIND", "0.0.0.0")
HTTP_PORT = int(os.getenv("HARNESS_HTTP_PORT", "8081"))

TUI_CMD = os.getenv("HARNESS_TUI_CMD", "codex")
DEFAULT_CWD = os.getenv("HARNESS_AGENT_WORKDIR", "/work")

JOBS = {}
JOBS_LOCK = threading.Lock()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sanitize_env(env: dict) -> dict:
    clean = {}
    for key, value in env.items():
        if not isinstance(key, str):
            continue
        if not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not all(c.isalnum() or c == "_" for c in key):
            continue
        clean[key] = str(value)
    return clean


def sanitize_cwd(cwd: str) -> str:
    if not cwd:
        return DEFAULT_CWD
    if not cwd.startswith("/work"):
        return DEFAULT_CWD
    return cwd


def ssh_base_args() -> list:
    return [
        "ssh",
        "-i",
        SSH_KEY_PATH,
        "-p",
        str(AGENT_PORT),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        f"UserKnownHostsFile={SSH_KNOWN_HOSTS}",
    ]


def ssh_target() -> str:
    return f"{AGENT_USER}@{AGENT_HOST}"


def build_remote_command(prompt: str, cwd: str, env: dict) -> str:
    env_parts = []
    for key, value in env.items():
        env_parts.append(f"{key}={shlex.quote(value)}")
    prefix = " ".join(env_parts)
    cmd = f"cd {shlex.quote(cwd)} && {prefix} codex exec {shlex.quote(prompt)}"
    return cmd.strip()


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def run_job(job_id: str, prompt: str, logged_prompt: str, cwd: str, env: dict, timeout: int | None) -> None:
    job_path = os.path.join(JOB_DIR, job_id)
    ensure_dir(job_path)
    stdout_path = os.path.join(job_path, "stdout.log")
    stderr_path = os.path.join(job_path, "stderr.log")
    status_path = os.path.join(job_path, "status.json")

    started_at = now_iso()
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["started_at"] = started_at
        JOBS[job_id]["output_path"] = stdout_path
        JOBS[job_id]["error_path"] = stderr_path

    meta = {
        "job_id": job_id,
        "submitted_at": JOBS[job_id]["submitted_at"],
        "started_at": started_at,
        "prompt": logged_prompt,
        "cwd": cwd,
        "env": env,
        "command": "codex exec",
    }
    write_json(os.path.join(job_path, "input.json"), meta)

    remote_cmd = build_remote_command(prompt, cwd, env)
    cmd = ssh_base_args() + [ssh_target(), "bash", "-lc", remote_cmd]

    with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
        proc = subprocess.Popen(cmd, stdout=out, stderr=err)
        status = "running"
        exit_code = None
        try:
            if timeout:
                proc.wait(timeout=timeout)
            else:
                proc.wait()
            exit_code = proc.returncode
            status = "complete" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            proc.kill()
            status = "failed"
            exit_code = 124

    with JOBS_LOCK:
        JOBS[job_id]["status"] = status
        JOBS[job_id]["ended_at"] = now_iso()
        JOBS[job_id]["exit_code"] = exit_code
        JOBS[job_id]["output_path"] = stdout_path
        JOBS[job_id]["error_path"] = stderr_path

    write_json(status_path, JOBS[job_id])


def handle_run(payload: dict) -> tuple[dict, int]:
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return {"error": "prompt is required"}, 400

    capture_input = payload.get("capture_input", True)
    logged_prompt = prompt if capture_input else "[redacted]"

    cwd = sanitize_cwd(str(payload.get("cwd", DEFAULT_CWD)))
    env = sanitize_env(payload.get("env", {}))
    timeout = payload.get("timeout_sec")
    timeout = int(timeout) if isinstance(timeout, (int, float)) and timeout > 0 else None

    job_id = f"job_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "submitted_at": now_iso(),
            "started_at": None,
            "ended_at": None,
            "exit_code": None,
            "output_path": None,
            "error_path": None,
        }

    ensure_dir(JOB_DIR)

    thread = threading.Thread(
        target=run_job,
        args=(job_id, prompt, logged_prompt, cwd, env, timeout),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "submitted_at": JOBS[job_id]["submitted_at"],
    }, 202


class HarnessHandler(BaseHTTPRequestHandler):
    def _json_response(self, payload: dict, status_code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/run":
            self._json_response({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length)) if length > 0 else {}
        except json.JSONDecodeError:
            self._json_response({"error": "invalid json"}, 400)
            return

        response, status = handle_run(payload)
        self._json_response(response, status)

    def do_GET(self) -> None:
        if not self.path.startswith("/jobs/"):
            self._json_response({"error": "not found"}, 404)
            return
        job_id = self.path[len("/jobs/") :]
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            self._json_response({"error": "unknown job"}, 404)
            return
        self._json_response(job, 200)

    def log_message(self, format: str, *args) -> None:
        return


def run_server() -> None:
    ensure_dir(LOG_DIR)
    ensure_dir(JOB_DIR)
    server = ThreadingHTTPServer((HTTP_BIND, HTTP_PORT), HarnessHandler)
    print(f"Harness HTTP server listening on {HTTP_BIND}:{HTTP_PORT}")
    server.serve_forever()


def run_tui() -> int:
    ensure_dir(LOG_DIR)
    ensure_dir(SESSION_DIR)

    session_id = f"session_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    session_path = os.path.join(SESSION_DIR, session_id)
    ensure_dir(session_path)

    stdin_path = os.path.join(session_path, "stdin.log")
    stdout_path = os.path.join(session_path, "stdout.log")
    meta_path = os.path.join(session_path, "meta.json")

    meta = {
        "session_id": session_id,
        "started_at": now_iso(),
        "mode": "tui",
        "command": TUI_CMD,
    }
    write_json(meta_path, meta)

    remote_cmd = f"cd {shlex.quote(DEFAULT_CWD)} && {TUI_CMD}"
    cmd = ssh_base_args() + ["-tt", ssh_target(), "bash", "-lc", remote_cmd]

    pid, master_fd = os.forkpty()
    if pid == 0:
        os.execvp(cmd[0], cmd)

    old_settings = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())

    sel = selectors.DefaultSelector()
    sel.register(sys.stdin, selectors.EVENT_READ)
    sel.register(master_fd, selectors.EVENT_READ)

    exit_code = 1
    with open(stdin_path, "ab") as stdin_log, open(stdout_path, "ab") as stdout_log:
        try:
            while True:
                for key, _ in sel.select():
                    if key.fileobj is sys.stdin:
                        data = os.read(sys.stdin.fileno(), 1024)
                        if not data:
                            os.close(master_fd)
                            break
                        os.write(master_fd, data)
                        stdin_log.write(data)
                        stdin_log.flush()
                    else:
                        data = os.read(master_fd, 1024)
                        if not data:
                            raise EOFError
                        os.write(sys.stdout.fileno(), data)
                        stdout_log.write(data)
                        stdout_log.flush()
        except EOFError:
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                exit_code = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                exit_code = 128 + os.WTERMSIG(status)
        finally:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)

    meta.update({
        "ended_at": now_iso(),
        "exit_code": exit_code,
        "stdin_path": stdin_path,
        "stdout_path": stdout_path,
    })
    write_json(meta_path, meta)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Harness control")
    parser.add_argument("mode", choices=["server", "tui"])
    args = parser.parse_args()

    if args.mode == "server":
        run_server()
        return 0
    return run_tui()


if __name__ == "__main__":
    raise SystemExit(main())
