import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SCRIPT = PROJECT_ROOT / "src" / "main.py"
MAX_OUTPUT_CHARS = 100_000
COMMANDS = {
    "collect": "collect",
    "validate": "validate",
    "linkedin": "linkedin",
    "open": "open-jobs",
    "open-career": "open-career-jobs",
}


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job Bot Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: Segoe UI, sans-serif; }
    body { margin: 0; background: #101827; color: #e5eaf2; }
    main { max-width: 900px; margin: 48px auto; padding: 0 24px; }
    h1 { margin-bottom: 8px; }
    p { color: #aab6c8; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin: 28px 0; }
    button { border: 0; border-radius: 8px; padding: 12px 22px;
      background: #3478f6; color: white; font-size: 16px; cursor: pointer; }
    button:hover:not(:disabled) { background: #5590ff; }
    button:disabled { opacity: .5; cursor: wait; }
    .logs-heading { display: flex; align-items: center; justify-content: space-between; }
    .logs-heading h2 { margin: 16px 0 8px; font-size: 18px; }
    #copy-logs { padding: 8px 14px; font-size: 14px; }
    #status { min-height: 24px; color: #aab6c8; }
    pre { min-height: 240px; max-height: 55vh; overflow: auto; padding: 16px;
      border: 1px solid #29364a; border-radius: 8px; background: #090e17;
      white-space: pre-wrap; overflow-wrap: anywhere; }
  </style>
</head>
<body>
  <main>
    <h1>Job Bot</h1>
    <p>Run a workflow command. Only one command can run at a time.</p>
    <div class="actions">
      <button data-command="collect">Collect</button>
      <button data-command="validate">Validate</button>
      <button data-command="linkedin">LinkedIn</button>
      <button data-command="open">Open jobs</button>
      <button data-command="open-career">Open career jobs</button>
    </div>
    <div id="status" role="status">Ready</div>
    <div class="logs-heading">
      <h2>Command output</h2>
      <button id="copy-logs" type="button">Copy logs</button>
    </div>
    <pre id="output" aria-live="polite"></pre>
  </main>
  <script>
    const buttons = [...document.querySelectorAll("[data-command]")];
    const status = document.getElementById("status");
    const output = document.getElementById("output");
    const copyButton = document.getElementById("copy-logs");

    async function refresh() {
      const response = await fetch("/api/status", { cache: "no-store" });
      const state = await response.json();
      buttons.forEach(button => button.disabled = state.running);
      status.textContent = state.running
        ? `Running: ${state.command}`
        : state.command
          ? `${state.command} finished (exit code ${state.return_code})`
          : "Ready";
      output.textContent = state.output || "";
    }

    buttons.forEach(button => button.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: button.dataset.command })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || response.statusText);
        await refresh();
      } catch (error) {
        status.textContent = `Could not start command: ${error.message}`;
      }
    }));

    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(output.textContent);
        status.textContent = "Logs copied to clipboard.";
      } catch (error) {
        status.textContent = `Could not copy logs: ${error.message}`;
      }
    });

    refresh().catch(error => {
      status.textContent = `Dashboard error: ${error.message}`;
    });
    window.setInterval(() => {
      refresh().catch(error => {
        status.textContent = `Dashboard error: ${error.message}`;
      });
    }, 1000);
  </script>
</body>
</html>
"""


class DashboardController:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            "running": False,
            "command": None,
            "return_code": None,
            "output": "",
        }
        self._process = None

    def state(self):
        with self._lock:
            return dict(self._state)

    def start_command(self, name):
        if name not in COMMANDS:
            return False

        with self._lock:
            if self._state["running"]:
                return False
            self._state = {
                "running": True,
                "command": name,
                "return_code": None,
                "output": f"Starting {name}...\n",
            }

        worker = threading.Thread(
            target=self._run_command,
            args=(name,),
            daemon=True,
        )
        worker.start()
        return True

    def _append_output(self, text):
        with self._lock:
            self._state["output"] = (
                self._state["output"] + text
            )[-MAX_OUTPUT_CHARS:]

    def _run_command(self, name):
        process = None
        try:
            child_env = os.environ.copy()
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env["PYTHONUTF8"] = "1"
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    str(MAIN_SCRIPT),
                    COMMANDS[name],
                ],
                cwd=PROJECT_ROOT,
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._process = process

            if process.stdout is None:
                raise RuntimeError("Command output stream was not created.")

            for line in process.stdout:
                self._append_output(line)
            return_code = process.wait()
        except Exception as exc:
            self._append_output(f"\n[dashboard error] {exc}\n")
            return_code = process.returncode if process is not None else -1
        finally:
            with self._lock:
                self._state["running"] = False
                self._state["return_code"] = return_code
                self._process = None


def _make_handler(controller):
    class DashboardHandler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _valid_local_host(self):
            host = self.headers.get("Host", "")
            try:
                parsed = urlsplit(f"http://{host}")
                port = parsed.port
            except ValueError:
                return False
            return (
                parsed.hostname in {"127.0.0.1", "localhost"}
                and port == self.server.server_port
            )

        def _valid_origin(self):
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            try:
                parsed = urlsplit(origin)
                port = parsed.port
            except ValueError:
                return False
            return (
                parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost"}
                and port == self.server.server_port
            )

        def do_GET(self):
            if not self._valid_local_host():
                self._send(403, "Local requests only.", "text/plain; charset=utf-8")
            elif self.path == "/":
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif self.path == "/api/status":
                self._send(
                    200,
                    json.dumps(controller.state()),
                    "application/json; charset=utf-8",
                )
            else:
                self._send(404, "Not found.", "text/plain; charset=utf-8")

        def do_POST(self):
            if not self._valid_local_host() or not self._valid_origin():
                self._send(403, json.dumps({"error": "Local requests only."}),
                           "application/json; charset=utf-8")
                return
            if self.path != "/api/run":
                self._send(404, json.dumps({"error": "Not found."}),
                           "application/json; charset=utf-8")
                return
            if self.headers.get_content_type() != "application/json":
                self._send(415, json.dumps({"error": "Expected JSON request."}),
                           "application/json; charset=utf-8")
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4096:
                    raise ValueError("Invalid request length.")
                payload = json.loads(self.rfile.read(length))
                name = payload.get("command") if isinstance(payload, dict) else None
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(400, json.dumps({"error": str(exc)}),
                           "application/json; charset=utf-8")
                return

            if not isinstance(name, str) or name not in COMMANDS:
                self._send(400, json.dumps({"error": "Unknown command."}),
                           "application/json; charset=utf-8")
                return
            if not controller.start_command(name):
                self._send(409, json.dumps({"error": "A command is already running."}),
                           "application/json; charset=utf-8")
                return
            self._send(202, json.dumps({"started": name}),
                       "application/json; charset=utf-8")

        def log_message(self, format, *args):
            if args and isinstance(args[0], int) and args[0] >= 400:
                super().log_message(format, *args)

    return DashboardHandler


def get_port():
    raw_port = os.environ.get("JOB_BOT_DASHBOARD_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid JOB_BOT_DASHBOARD_PORT value: {raw_port!r}"
        ) from exc
    if not 0 < port < 65536:
        raise RuntimeError(
            f"JOB_BOT_DASHBOARD_PORT must be between 1 and 65535; got {port}."
        )
    return port


def run():
    controller = DashboardController()
    server = ThreadingHTTPServer(
        (HOST, get_port()),
        _make_handler(controller),
    )
    url = f"http://{HOST}:{server.server_port}/"
    print(f"Job Bot dashboard running at {url}")
    print("Press Ctrl+C to stop the dashboard.")
    if not webbrowser.open(url):
        print(f"[INFO] Open this URL in your browser: {url}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Job Bot dashboard.")
    finally:
        server.server_close()
