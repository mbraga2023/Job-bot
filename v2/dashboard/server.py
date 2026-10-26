"""Embedded Web Dashboard Server for Job-bot Version 2.0."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from v2.core.database import (
    delete_non_qa_jobs,
    get_career_sources,
    get_database_stats,
    get_non_qa_job_count,
    insert_career_source,
    set_career_source_active,
    update_career_source,
)
from v2.dashboard.pages.companies import PAGE_HTML as COMPANIES_PAGE_HTML
from v2.dashboard.pages.dashboard import PAGE_HTML as DASHBOARD_PAGE_HTML

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STYLESHEET_PATH = Path(__file__).resolve().parent / "style" / "dashboard.css"
MAIN_SCRIPT = PROJECT_ROOT / "v2" / "main.py"
HOST = "127.0.0.1"
DEFAULT_PORT = 8766
OLLAMA_API_URL = "http://127.0.0.1:11434/api/tags"
MAX_OUTPUT_CHARS = 100_000
PAGE_HTML = DASHBOARD_PAGE_HTML

# Process state
ACTIVE_PROCESS: subprocess.Popen | None = None
OLLAMA_PROCESS: subprocess.Popen | None = None
ACTIVE_PROCESS_LOCK = threading.Lock()
OLLAMA_PROCESS_LOCK = threading.Lock()
COMMAND_OUTPUT: list[str] = []
COMMAND_OUTPUT_LOCK = threading.Lock()
CURRENT_COMMAND: str | None = None


def is_ollama_running() -> bool:
    """Check whether the local Ollama API is responding."""
    try:
        with urlopen(OLLAMA_API_URL, timeout=2) as response:
            return response.status == 200
    except (URLError, TimeoutError, OSError):
        return False


def start_ollama() -> tuple[bool, bool, str | None]:
    """Start Ollama's local service if it is not already responding."""
    global OLLAMA_PROCESS
    if is_ollama_running():
        return True, False, None

    executable = shutil.which("ollama")
    if executable is None:
        return False, False, "Ollama executable was not found on PATH."

    with OLLAMA_PROCESS_LOCK:
        if is_ollama_running():
            return True, False, None

        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        try:
            OLLAMA_PROCESS = subprocess.Popen(
                [executable, "serve"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
        except OSError as exc:
            return False, False, f"Could not start Ollama: {exc}"

    return True, True, None


def stop_dashboard_ollama() -> tuple[bool, str | None]:
    """Stop Ollama, including an instance already running before this dashboard."""
    global OLLAMA_PROCESS
    with OLLAMA_PROCESS_LOCK:
        process = OLLAMA_PROCESS
        if process is not None:
            if process.poll() is not None:
                OLLAMA_PROCESS = None
                return True, None
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    return False, f"Could not stop dashboard-started Ollama: {exc}"
            except OSError as exc:
                return False, f"Could not stop dashboard-started Ollama: {exc}"

            OLLAMA_PROCESS = None
            return True, None

    return stop_external_ollama()


def stop_external_ollama() -> tuple[bool, str | None]:
    """Stop an Ollama process listening on port 11434 without killing other apps."""
    if sys.platform != "win32":
        return False, "Cannot identify an independently started Ollama process on this platform."

    powershell = shutil.which("powershell")
    if powershell is None:
        return False, "PowerShell is required to find the Ollama process listening on port 11434."

    query_script = (
        "$ErrorActionPreference = 'Stop'; "
        "$connections = @(Get-NetTCPConnection -LocalPort 11434 -State Listen "
        "-ErrorAction SilentlyContinue); "
        "$processes = @($connections | Select-Object -ExpandProperty OwningProcess -Unique | "
        "ForEach-Object { $p = Get-Process -Id $_ -ErrorAction SilentlyContinue; "
        "if ($p) { [pscustomobject]@{ Id = $p.Id; Name = $p.ProcessName } } }); "
        "ConvertTo-Json -InputObject $processes -Compress"
    )
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", query_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not identify the Ollama listener: {exc}"

    if result.returncode != 0:
        detail = result.stderr.strip() or "PowerShell returned an error."
        return False, f"Could not identify the Ollama listener: {detail}"

    try:
        processes = json.loads(result.stdout.strip() or "[]")
    except json.JSONDecodeError as exc:
        return False, f"Could not parse the Ollama listener details: {exc}"

    if isinstance(processes, dict):
        processes = [processes]
    if not isinstance(processes, list):
        return False, "PowerShell returned invalid Ollama listener details."

    pids: list[int] = []
    for process in processes:
        if not isinstance(process, dict):
            return False, "PowerShell returned invalid Ollama listener details."
        process_id = process.get("Id")
        process_name = process.get("Name")
        if not isinstance(process_id, int) or process_id <= 0 or not isinstance(process_name, str):
            return False, "PowerShell returned invalid Ollama listener details."
        if process_name.casefold() != "ollama":
            return False, (
                f"Port 11434 is owned by '{process_name}', not Ollama; "
                "the dashboard left it running."
            )
        pids.append(process_id)

    for process_id in pids:
        stop_script = (
            f"$p = Get-Process -Id {process_id} -ErrorAction SilentlyContinue; "
            "if ($p -and $p.ProcessName -ine 'ollama') { "
            "throw 'The listener process changed; refusing to stop it.' }; "
            f"Stop-Process -Id {process_id}; "
            f"Wait-Process -Id {process_id} -Timeout 5 -ErrorAction SilentlyContinue; "
            f"Get-Process -Id {process_id} -ErrorAction SilentlyContinue | "
            "Where-Object ProcessName -EQ 'ollama' | "
            "Stop-Process -Force -ErrorAction SilentlyContinue"
        )
        try:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", stop_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"Could not stop Ollama process {process_id}: {exc}"
        if result.returncode != 0:
            detail = result.stderr.strip() or "PowerShell returned an error."
            return False, f"Could not stop Ollama process {process_id}: {detail}"

    return True, None


def stop_active_command() -> tuple[bool, str | None]:
    """Stop the command currently running from the dashboard, if any."""
    with ACTIVE_PROCESS_LOCK:
        process = ACTIVE_PROCESS
        if process is None or process.poll() is not None:
            return True, None

        try:
            process.terminate()
            append_output("\n>> Command stopped because the dashboard is closing.\n")
        except OSError as exc:
            return False, f"Could not stop the active command: {exc}"

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"Could not stop the active command: {exc}"
    except OSError as exc:
        return False, f"Could not stop the active command: {exc}"

    return True, None


def request_server_shutdown(httpd: ThreadingHTTPServer) -> None:
    """Stop serve_forever from a separate thread after the close response is sent."""
    threading.Thread(target=httpd.shutdown, daemon=True).start()


def append_output(text: str) -> None:
    """Append text to shared output log."""
    with COMMAND_OUTPUT_LOCK:
        COMMAND_OUTPUT.append(text)
        total = sum(len(chunk) for chunk in COMMAND_OUTPUT)
        while total > MAX_OUTPUT_CHARS and COMMAND_OUTPUT:
            removed = COMMAND_OUTPUT.pop(0)
            total -= len(removed)


def get_logs() -> str:
    """Retrieve concatenated log output."""
    with COMMAND_OUTPUT_LOCK:
        return "".join(COMMAND_OUTPUT)


def run_command_in_background(cmd_args: list[str], label: str) -> bool:
    """Start command in background thread."""
    global ACTIVE_PROCESS, CURRENT_COMMAND
    with ACTIVE_PROCESS_LOCK:
        if ACTIVE_PROCESS is not None and ACTIVE_PROCESS.poll() is None:
            return False

        CURRENT_COMMAND = label
        append_output(f"\n>> Running: {label}\n")

        # Use the same python executable
        cmd = [sys.executable, str(MAIN_SCRIPT)] + cmd_args

        try:
            ACTIVE_PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except Exception as exc:
            append_output(f"Failed to start process: {exc}\n")
            CURRENT_COMMAND = None
            ACTIVE_PROCESS = None
            return False

        process = ACTIVE_PROCESS

    def reader():
        global ACTIVE_PROCESS, CURRENT_COMMAND
        proc = process
        if proc and proc.stdout:
            for line in proc.stdout:
                append_output(line)
        if proc:
            proc.wait()
            append_output(f"\n>> Process finished with exit code {proc.returncode}\n")
        with ACTIVE_PROCESS_LOCK:
            if ACTIVE_PROCESS == proc:
                ACTIVE_PROCESS = None
                CURRENT_COMMAND = None

    threading.Thread(target=reader, daemon=True).start()
    return True


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for local web UI and JSON endpoints."""

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(body) if body else {}
        if not isinstance(data, dict):
            raise ValueError("A JSON object is required.")
        return data

    def _send_json(self, status_code: int, payload: dict) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _company_id(self) -> int | None:
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "companies"]:
            return None
        try:
            company_id = int(parts[2])
        except ValueError:
            return None
        return company_id if company_id > 0 else None

    def log_message(self, format, *args):
        # Silence default stderr logging
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGE_HTML.encode("utf-8"))
            return

        if parsed.path == "/companies":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(COMPANIES_PAGE_HTML.encode("utf-8"))
            return

        if parsed.path == "/style/dashboard.css":
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.end_headers()
            self.wfile.write(STYLESHEET_PATH.read_bytes())
            return

        if parsed.path == "/api/companies":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"companies": get_career_sources()}).encode("utf-8"))
            return

        if parsed.path == "/api/stats":
            stats = get_database_stats()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode("utf-8"))
            return

        if parsed.path == "/api/ollama/status":
            running = is_ollama_running()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"running": running}).encode("utf-8"))
            return

        if parsed.path == "/api/non-qa-jobs":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"count": get_non_qa_job_count()}).encode("utf-8"))
            return

        if parsed.path == "/api/logs":
            with ACTIVE_PROCESS_LOCK:
                running = ACTIVE_PROCESS is not None and ACTIVE_PROCESS.poll() is None
            resp = {
                "logs": get_logs(),
                "running": running,
                "command": CURRENT_COMMAND,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlsplit(self.path)

        if parsed.path == "/api/run":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            args = data.get("args", [])
            label = data.get("label", "Command")
            started = run_command_in_background(args, label)

            self.send_response(200 if started else 409)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"started": started}).encode("utf-8"))
            return

        if parsed.path == "/api/stop":
            global ACTIVE_PROCESS
            with ACTIVE_PROCESS_LOCK:
                if ACTIVE_PROCESS and ACTIVE_PROCESS.poll() is None:
                    ACTIVE_PROCESS.terminate()
                    append_output("\n>> Command stopped by user.\n")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"stopped": True}).encode("utf-8"))
            return

        if parsed.path == "/api/ollama/start":
            succeeded, started, error = start_ollama()
            self.send_response(200 if succeeded else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"started": started, "error": error}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        if parsed.path == "/api/close":
            ollama_stopped, error = stop_dashboard_ollama()
            if ollama_stopped:
                command_stopped, error = stop_active_command()
            else:
                command_stopped = False

            if not ollama_stopped or not command_stopped:
                self.send_response(503)
                response = {"closed": False, "error": error}
            else:
                self.send_response(200)
                response = {"closed": True}
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            self.wfile.flush()
            if response["closed"]:
                request_server_shutdown(self.server)
            return

        if parsed.path == "/api/non-qa-jobs":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
            if data.get("confirmation") != "DELETE NON-QA JOBS":
                self.send_response(400)
                response = {"error": "Explicit cleanup confirmation is required."}
            elif not isinstance(data.get("expected_count"), int) or isinstance(
                data.get("expected_count"), bool
            ):
                self.send_response(400)
                response = {"error": "A valid preview count is required."}
            else:
                try:
                    deleted = delete_non_qa_jobs(data["expected_count"])
                except ValueError as exc:
                    self.send_response(409)
                    response = {"error": str(exc)}
                else:
                    self.send_response(200)
                    response = {"deleted": deleted}
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        if parsed.path == "/api/import-career":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            company = data.get("company", "").strip()
            careers_url = data.get("careers_url", "").strip()
            search_url = data.get("search_url", "").strip() or None
            is_international = data.get("is_international", False)

            if not isinstance(is_international, bool):
                self.send_response(400)
                response = {"ok": False, "error": "is_international must be a boolean."}
            elif not company or not careers_url:
                self.send_response(400)
                response = {"ok": False, "error": "Company and careers URL are required."}
            else:
                row_id = insert_career_source(
                    company,
                    careers_url,
                    search_url,
                    is_international=is_international,
                )
                self.send_response(200)
                response = {"ok": True, "duplicate": row_id == 0}

            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_PUT(self):
        company_id = self._company_id()
        if company_id is None:
            self._send_json(400, {"error": "A valid company ID is required."})
            return

        try:
            data = self._read_json_body()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._send_json(400, {"error": f"Invalid request body: {exc}"})
            return

        company = data.get("company")
        careers_url = data.get("careers_url")
        search_url = data.get("search_url", "")
        is_international = data.get("is_international")
        if (
            not isinstance(company, str)
            or not company.strip()
            or not isinstance(careers_url, str)
            or not careers_url.strip()
            or not isinstance(search_url, str)
            or not isinstance(is_international, bool)
        ):
            self._send_json(
                400,
                {"error": "Company, careers URL, and boolean is_international are required."},
            )
            return

        try:
            updated = update_career_source(
                company_id,
                company,
                careers_url,
                search_url or None,
                is_international,
            )
        except sqlite3.IntegrityError:
            self._send_json(409, {"error": "That careers URL is already registered."})
            return
        if not updated:
            self._send_json(404, {"error": "Company was not found."})
            return
        self._send_json(200, {"ok": True})

    def do_PATCH(self):
        company_id = self._company_id()
        if company_id is None:
            self._send_json(400, {"error": "A valid company ID is required."})
            return

        try:
            data = self._read_json_body()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._send_json(400, {"error": f"Invalid request body: {exc}"})
            return

        active = data.get("active")
        if not isinstance(active, bool):
            self._send_json(400, {"error": "A boolean active value is required."})
            return
        if not set_career_source_active(company_id, active):
            self._send_json(404, {"error": "Company was not found."})
            return
        self._send_json(200, {"ok": True, "active": active})


def run_server(port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    """Start threaded HTTP server and optionally open browser."""
    server_address = (HOST, port)
    httpd = ThreadingHTTPServer(server_address, DashboardHandler)
    url = f"http://{HOST}:{port}/"
    print("\n" + "=" * 60)
    print(f"🚀 Job-bot v2.0 Dashboard running at: {url}")
    print("   Press Ctrl+C to stop.")
    print("=" * 60 + "\n")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
    finally:
        httpd.server_close()
