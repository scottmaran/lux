#!/usr/bin/env python3
import argparse
import datetime as dt
import fcntl
import json
import os
import selectors
import shlex
import signal
import struct
import socket
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
LABELS_DIR = os.path.join(LOG_DIR, "labels")
SESSION_LABEL_DIR = os.path.join(LABELS_DIR, "sessions")
JOB_LABEL_DIR = os.path.join(LABELS_DIR, "jobs")

AGENT_HOST = os.getenv("HARNESS_AGENT_HOST", "agent")
AGENT_PORT = int(os.getenv("HARNESS_AGENT_PORT", "22"))
AGENT_USER = os.getenv("HARNESS_AGENT_USER", "agent")
SSH_KEY_PATH = os.getenv("HARNESS_SSH_KEY_PATH", "/harness/keys/ssh_key")
SSH_KNOWN_HOSTS = os.getenv("HARNESS_SSH_KNOWN_HOSTS", "/harness/keys/known_hosts")
SSH_WAIT_SEC = int(os.getenv("HARNESS_SSH_WAIT_SEC", "30"))

HTTP_BIND = os.getenv("HARNESS_HTTP_BIND", "0.0.0.0")
HTTP_PORT = int(os.getenv("HARNESS_HTTP_PORT", "8081"))
API_TOKEN = os.getenv("HARNESS_API_TOKEN", "")

TUI_CMD = os.getenv("HARNESS_TUI_CMD", "codex -C /work -s danger-full-access")
RUN_CMD_TEMPLATE = os.getenv("HARNESS_RUN_CMD_TEMPLATE", "").strip() or "codex -C /work -s danger-full-access exec {prompt}"
DEFAULT_CWD = os.getenv("HARNESS_AGENT_WORKDIR", "/work")

JOBS = {}
JOBS_LOCK = threading.Lock()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def wait_for_agent(timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with socket.create_connection((AGENT_HOST, AGENT_PORT), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def wait_for_agent_ssh(timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not wait_for_agent(2):
            time.sleep(1)
            continue
        cmd = ssh_base_args() + [
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=2",
            ssh_target(),
            "true",
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return True
        time.sleep(1)
    return False


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
    base = os.path.realpath(DEFAULT_CWD)
    if not cwd:
        return base
    if not os.path.isabs(cwd):
        return base
    real = os.path.realpath(cwd)
    if real == base or real.startswith(base + os.sep):
        return real
    return base


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


def get_terminal_size() -> os.terminal_size:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            size = os.get_terminal_size(stream.fileno())
            if size.columns > 1 and size.lines > 1:
                return size
        except OSError:
            continue
    env_cols = os.getenv("COLUMNS")
    env_lines = os.getenv("LINES")
    try:
        if env_cols and env_lines:
            cols = int(env_cols)
            lines = int(env_lines)
            if cols > 1 and lines > 1:
                return os.terminal_size((cols, lines))
    except ValueError:
        pass
    return os.terminal_size((80, 24))

def set_pty_size(fd: int, size: os.terminal_size | None = None) -> None:
    size = size or get_terminal_size()
    rows, cols = size.lines, size.columns
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def build_remote_command(prompt: str, cwd: str, env: dict, timeout: int | None) -> str:
    env_parts = []
    for key, value in env.items():
        env_parts.append(f"{key}={shlex.quote(value)}")
    prefix = " ".join(env_parts)
    cmd = f"cd {shlex.quote(cwd)} && "
    if prefix:
        cmd += f"{prefix} "
    if timeout:
        cmd += f"timeout {int(timeout)} "
    if "{prompt}" in RUN_CMD_TEMPLATE:
        run_cmd = RUN_CMD_TEMPLATE.replace("{prompt}", shlex.quote(prompt))
    else:
        run_cmd = RUN_CMD_TEMPLATE
    cmd += run_cmd
    return cmd.strip()


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def normalize_label_name(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, "name must be a string"
    trimmed = value.strip()
    if not trimmed:
        return None, "name must not be empty"
    return trimmed, None


def write_label(dir_path: str, run_id: str, name: str) -> None:
    ensure_dir(dir_path)
    label_path = os.path.join(dir_path, f"{run_id}.json")
    payload = {"name": name, "updated_at": now_iso()}
    write_json(label_path, payload)


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
        "command": RUN_CMD_TEMPLATE,
    }
    write_json(os.path.join(job_path, "input.json"), meta)

    if not wait_for_agent_ssh(SSH_WAIT_SEC):
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["ended_at"] = now_iso()
            JOBS[job_id]["exit_code"] = 255
            JOBS[job_id]["error"] = "agent_unreachable"
        write_json(status_path, JOBS[job_id])
        return

    remote_cmd = build_remote_command(prompt, cwd, env, timeout)
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
                JOBS[job_id]["error"] = "timeout"

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

    name, name_err = normalize_label_name(payload.get("name"))
    if name_err:
        return {"error": name_err}, 400

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
            "error": None,
            "output_path": None,
            "error_path": None,
        }

    ensure_dir(JOB_DIR)
    if name:
        write_label(JOB_LABEL_DIR, job_id, name)

    thread = threading.Thread(
        target=run_job,
        args=(job_id, prompt, logged_prompt, cwd, env, timeout),
        daemon=True,
    )
    thread.start()

    response = {
        "job_id": job_id,
        "status": "queued",
        "submitted_at": JOBS[job_id]["submitted_at"],
    }
    if name:
        response["name"] = name
    return response, 202


class HarnessHandler(BaseHTTPRequestHandler):
    def _json_response(self, payload: dict, status_code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        token = self.headers.get("X-Harness-Token", "")
        if not token or token != API_TOKEN:
            self._json_response({"error": "unauthorized"}, 401)
            return False
        return True

    def do_POST(self) -> None:
        if not self._authorized():
            return
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
        if not self._authorized():
            return
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
    if not API_TOKEN:
        print("HARNESS_API_TOKEN is required for server mode.", file=sys.stderr)
        raise SystemExit(2)
    ensure_dir(LOG_DIR)
    ensure_dir(JOB_DIR)
    server = ThreadingHTTPServer((HTTP_BIND, HTTP_PORT), HarnessHandler)
    print(f"Harness HTTP server listening on {HTTP_BIND}:{HTTP_PORT}")
    server.serve_forever()


def resolve_tui_name(cli_name: str | None) -> tuple[str | None, str | None]:
    if cli_name is not None:
        trimmed = cli_name.strip()
        if not trimmed:
            return None, "tui name must not be empty"
        return trimmed, None
    env_value = os.getenv("HARNESS_TUI_NAME")
    if env_value is None:
        return None, None
    trimmed = env_value.strip()
    if not trimmed:
        return None, "HARNESS_TUI_NAME must not be empty"
    return trimmed, None


def run_tui(tui_name: str | None) -> int:
    ensure_dir(LOG_DIR)
    ensure_dir(SESSION_DIR)

    label_name, label_err = resolve_tui_name(tui_name)
    if label_err:
        print(label_err, file=sys.stderr)
        return 2

    if not wait_for_agent_ssh(SSH_WAIT_SEC):
        print("Agent SSH is not ready (auth failed or port unreachable). Try again in a few seconds.", file=sys.stderr)
        return 1

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
    if label_name:
        write_label(SESSION_LABEL_DIR, session_id, label_name)

    remote_cmd = f"cd {shlex.quote(DEFAULT_CWD)} && {TUI_CMD}" # e.g. cd /work && codex
    cmd = ssh_base_args() + ["-tt", ssh_target(), "bash", "-lc", remote_cmd] # Build the ssh command with -tt (force PTY allocation)

    ''' 
    creates a new PTY and forks:
      - Child execs the ssh command so the TUI runs inside a PTY.
      - Parent gets the PTY master fd (master_fd).
    '''
    term_size = get_terminal_size()
    pid, master_fd = os.forkpty()
    if pid == 0:
        try:
            set_pty_size(sys.stdin.fileno(), term_size)
        except OSError:
            pass
        os.execvp(cmd[0], cmd)

    try:
        set_pty_size(master_fd, term_size)
    except OSError:
        pass
    signal.signal(signal.SIGWINCH, lambda *_: set_pty_size(master_fd))

    # Terminal mode + IO multiplexing
    old_settings = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno()) # keystrokes pass through unchanged

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
        except (EOFError, OSError):
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
    parser.add_argument("--tui-name", dest="tui_name", help="Human-friendly name for TUI sessions")
    args = parser.parse_args()

    if args.mode == "server":
        run_server()
        return 0
    return run_tui(args.tui_name)


if __name__ == "__main__":
    raise SystemExit(main())
