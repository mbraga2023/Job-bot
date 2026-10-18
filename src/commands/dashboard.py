import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from database.career_sources import insert_career_sources

HOST = "127.0.0.1"
DEFAULT_PORT = 8766
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SCRIPT = PROJECT_ROOT / "src" / "main.py"
MAX_OUTPUT_CHARS = 100_000
MAX_CAREER_SOURCE_REQUEST_BYTES = 2 * 1024 * 1024
COMMANDS = {
    "collect": "collect",
    "validate": "validate",
    "careers": "careers",
    "linkedin": "linkedin",
    "open": "open-jobs",
    "open-career": "open-career-jobs",
    "validate-career-jobs": "validate-career-jobs",
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
    main { max-width: 1400px; margin: 48px auto; padding: 0 24px; }
    .dashboard-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
      align-items: start; gap: 40px; }
    .terminal-panel { min-width: 0; }
    h1 { margin-bottom: 8px; }
    p { color: #aab6c8; }
    .action-group { margin: 28px 0; }
    .action-group h2 { margin: 0 0 10px; font-size: 16px; color: #aab6c8; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; }
    .career-platform-options { display: flex; gap: 18px; margin: 0 0 12px;
      padding: 0; border: 0; color: #aab6c8; }
    .career-platform-options label { display: flex; align-items: center; gap: 8px; }
    .source-form { display: grid; gap: 12px; max-width: 620px; }
    .source-form label { display: grid; gap: 6px; color: #aab6c8; }
    .source-form input { box-sizing: border-box; width: 100%; padding: 10px;
      border: 1px solid #29364a; border-radius: 6px; background: #090e17;
      color: #e5eaf2; font: inherit; }
    .source-form button { justify-self: start; }
    .source-form .form-status { min-height: 20px; margin: 0; }
    button { border: 0; border-radius: 8px; padding: 12px 22px;
      background: #3478f6; color: white; font-size: 16px; cursor: pointer; }
    button:hover:not(:disabled) { background: #5590ff; }
    button:disabled { opacity: .5; cursor: wait; }
    #stop-command { background: #bd3545; }
    #stop-command:hover:not(:disabled) { background: #dc4658; }
    .logs-heading { display: flex; align-items: center; justify-content: space-between; }
    .logs-heading h2 { margin: 16px 0 8px; font-size: 18px; }
    .logs-actions { display: flex; gap: 8px; }
    #copy-logs { padding: 8px 14px; font-size: 14px; }
    #export-logs { padding: 8px 14px; font-size: 14px; }
    #status { min-height: 24px; color: #aab6c8; }
    pre { min-height: 240px; max-height: 55vh; overflow: auto; padding: 16px;
      border: 1px solid #29364a; border-radius: 8px; background: #090e17;
      white-space: pre-wrap; overflow-wrap: anywhere; }
    /* Import careers modal: hidden by default */
#career-source-import {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 1000;
  padding: 24px;
  box-sizing: border-box;
  overflow-y: auto;
  background: rgb(0 0 0 / 70%);
  align-items: center;
  justify-content: center;
}

#career-source-import.is-open {
  display: flex;
}

#career-source-import .modal-content {
  width: min(620px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  box-sizing: border-box;
  padding: 24px;
  border: 1px solid #29364a;
  border-radius: 12px;
  background: #101827;
  box-shadow: 0 20px 60px rgb(0 0 0 / 40%);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.modal-header h2 {
  margin: 0 0 20px;
}

#close-career-source-modal {
  padding: 6px 12px;
  background: #29364a;
  font-size: 14px;
}
    @media (max-width: 800px) {
      main { margin: 24px auto; }
      .dashboard-layout { grid-template-columns: minmax(0, 1fr); gap: 24px; }
    }
  </style>
</head>
<body>
  <main>
    <div class="dashboard-layout">
      <section class="controls-panel" aria-label="Dashboard controls">
        <h1>Job Bot</h1>
        <p>Run a workflow command. Only one command can run at a time.</p>
        <section class="action-group" id="telegram-linkedin-flow">
          <h2>Telegram / LinkedIn flow</h2>
          <div class="actions">
            <button data-command="collect">Collect</button>
            <button data-command="validate">Validate</button>
            <button data-command="linkedin">LinkedIn</button>
            <button data-command="open">Open jobs</button>
          </div>
        </section>
        <section class="action-group" id="career-flow">
          <h2>Career flow</h2>
          <fieldset class="career-platform-options">
            <legend>Career search platform</legend>
            <label>
              <input
                id="career-platform-inhire"
                type="checkbox"
                name="career-platform"
                value="inhire"
              >
              InHire
            </label>
            <label>
              <input
                id="career-platform-search-all"
                type="checkbox"
                name="career-platform"
                value="search_all"
                checked
              >
              Search All
            </label>
          </fieldset>
          <div class="actions">
            <button data-command="careers">Careers</button>
            <button data-command="validate-career-jobs">Validate career jobs</button>
            <button data-command="open-career">Open career jobs</button>
            <button id="show-career-source-form" type="button">Import careers</button>
          </div>
        </section>
        <section
  class="action-group"
  id="career-source-import"
  role="dialog"
  aria-modal="true"
  aria-labelledby="career-source-modal-title"
  aria-hidden="true"
>
  <div class="modal-content">
    <div class="modal-header">
      <h2 id="career-source-modal-title">Add career sources</h2>
      <button id="close-career-source-modal"
              type="button"
              aria-label="Close import modal">
        Close
      </button>
    </div>

    <form id="career-source-form" class="source-form">
      <label>
        Company name
        <input name="company" type="text" required maxlength="200">
      </label>

      <label>
        Company careers / jobs page URL
        <input name="careers_url" type="url" required>
      </label>

      <label>
        Search URL (optional)
        <input name="search_url" type="url">
      </label>

      <button type="submit">Save company</button>
      <p id="career-source-status" class="form-status" role="status"></p>
    </form>

    <form id="career-source-batch-form" class="source-form">
      <label>
        Upload a JSON file to import multiple companies
        <input name="file" type="file" accept=".json,application/json" required>
      </label>

      <button type="submit">Upload JSON batch</button>
      <p id="career-source-batch-status" class="form-status" role="status"></p>
    </form>
  </div>
</section>

      </section>
      <section class="terminal-panel" aria-label="Command terminal">
        <div class="logs-heading">
          <h2>Command output</h2>
        </div>
        <pre id="output" aria-live="polite"></pre>
                  <h2>Log actions</h2>
          <div class="logs-actions">
            <button id="copy-logs" type="button">Copy logs</button>
            <button id="export-logs" type="button" disabled>Export logs (.txt)</button>
                    <div id="status" role="status">Ready</div>
        <button id="stop-command" type="button" disabled>Stop command</button>
          </div>
      </section>
    </div>
  </main>
  <script>
    const buttons = [...document.querySelectorAll("[data-command]")];
    const status = document.getElementById("status");
    const output = document.getElementById("output");
    const copyButton = document.getElementById("copy-logs");
    const exportButton = document.getElementById("export-logs");
    const stopButton = document.getElementById("stop-command");
    const showCareerSourceFormButton = document.getElementById("show-career-source-form");
    const careerSourceModal = document.getElementById("career-source-import");
    const closeCareerSourceModalButton = document.getElementById(
      "close-career-source-modal"
    );
    const careerSourceForm = document.getElementById("career-source-form");
    const careerSourceBatchForm = document.getElementById("career-source-batch-form");
    const careerPlatformOptions = [
      ...document.querySelectorAll('input[name="career-platform"]')
    ];

    careerPlatformOptions.forEach(option => {
      option.addEventListener("change", () => {
        if (option.checked) {
          careerPlatformOptions.forEach(other => {
            if (other !== option) other.checked = false;
          });
        } else if (!careerPlatformOptions.some(item => item.checked)) {
          option.checked = true;
        }
      });
    });

    function openCareerSourceModal() {
      careerSourceModal.classList.add("is-open");
      careerSourceModal.setAttribute("aria-hidden", "false");
      careerSourceForm.elements.company.focus();
    }

    function closeCareerSourceModal() {
      careerSourceModal.classList.remove("is-open");
      careerSourceModal.setAttribute("aria-hidden", "true");
      showCareerSourceFormButton.focus();
    }

    showCareerSourceFormButton.addEventListener(
      "click",
      openCareerSourceModal
    );

    closeCareerSourceModalButton.addEventListener(
      "click",
      closeCareerSourceModal
    );

    careerSourceModal.addEventListener("click", event => {
      if (event.target === careerSourceModal) {
        closeCareerSourceModal();
      }
    });

    document.addEventListener("keydown", event => {
      if (
        event.key === "Escape" &&
        careerSourceModal.classList.contains("is-open")
      ) {
        closeCareerSourceModal();
      }
    });

    async function saveCareerSources(sources, targetStatus) {
      targetStatus.textContent = "Saving career sources...";
      const response = await fetch("/api/career-sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || response.statusText);
      targetStatus.textContent =
        `Added ${result.inserted}; skipped ${result.skipped} existing.`;
    }

    careerSourceForm.addEventListener("submit", async event => {
      event.preventDefault();
      const targetStatus = document.getElementById("career-source-status");
      const fields = new FormData(careerSourceForm);
      const source = Object.fromEntries(fields.entries());
      source.search_url = source.search_url.trim() || null;
      try {
        await saveCareerSources([source], targetStatus);
        careerSourceForm.reset();
      } catch (error) {
        targetStatus.textContent = `Could not save company: ${error.message}`;
      }
    });

    careerSourceBatchForm.addEventListener("submit", async event => {
      event.preventDefault();
      const targetStatus = document.getElementById("career-source-batch-status");
      const file = new FormData(careerSourceBatchForm).get("file");
      if (!(file instanceof File)) {
        targetStatus.textContent = "Select a JSON file to upload.";
        return;
      }
      try {
        const sources = JSON.parse(await file.text());
        await saveCareerSources(sources, targetStatus);
        careerSourceBatchForm.reset();
      } catch (error) {
        targetStatus.textContent = `Could not import JSON: ${error.message}`;
      }
    });

    async function refresh() {
      const response = await fetch("/api/status", { cache: "no-store" });
      const state = await response.json();
      buttons.forEach(button => button.disabled = state.running);
      stopButton.disabled = !state.running || state.stopping;
      exportButton.disabled = !state.output;
      status.textContent = state.running
        ? state.stopping
          ? `Stopping: ${state.command}`
          : `Running: ${state.command}`
        : state.command
          ? `${state.command} ${state.stopped ? "stopped" : "finished"} (exit code ${state.return_code})`
          : "Ready";
      output.textContent = state.output || "";
    }

    buttons.forEach(button => button.addEventListener("click", async () => {
      try {
        const payload = { command: button.dataset.command };
        if (button.dataset.command === "careers") {
          payload.career_platform = careerPlatformOptions.find(
            option => option.checked
          ).value;
        }
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || response.statusText);
        await refresh();
      } catch (error) {
        status.textContent = `Could not start command: ${error.message}`;
      }
    }));

    stopButton.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/stop", { method: "POST" });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || response.statusText);
        await refresh();
      } catch (error) {
        status.textContent = `Could not stop command: ${error.message}`;
      }
    });

    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(output.textContent);
        status.textContent = "Logs copied to clipboard.";
      } catch (error) {
        status.textContent = `Could not copy logs: ${error.message}`;
      }
    });

    exportButton.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/logs", { cache: "no-store" });
        if (!response.ok) throw new Error(await response.text());
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "job-bot-logs.txt";
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        status.textContent = "Logs exported to a text file.";
      } catch (error) {
        status.textContent = `Could not export logs: ${error.message}`;
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
            "stopping": False,
            "stopped": False,
            "command": None,
            "return_code": None,
            "output": "",
        }
        self._all_output = tempfile.SpooledTemporaryFile(
            max_size=MAX_OUTPUT_CHARS,
            mode="w+t",
            encoding="utf-8",
        )
        self._process = None
        self._stop_requested = False

    def state(self):
        with self._lock:
            return dict(self._state)

    def logs_for_export(self):
        with self._lock:
            self._all_output.seek(0)
            output = self._all_output.read()
            self._all_output.seek(0, os.SEEK_END)
            return self._state["command"], output

    def close(self):
        with self._lock:
            self._all_output.close()

    def start_command(self, name, career_platform="search_all"):
        if name not in COMMANDS:
            return False
        if name == "careers":
            if not isinstance(career_platform, str) or career_platform not in {
                "search_all",
                "inhire",
            }:
                return False

        with self._lock:
            if self._state["running"]:
                return False
            self._state = {
                "running": True,
                "stopping": False,
                "stopped": False,
                "command": name,
                "career_platform": career_platform if name == "careers" else None,
                "return_code": None,
                "output": f"Starting {name}...\n",
            }
            self._all_output.seek(0)
            self._all_output.truncate()
            self._all_output.write(f"Starting {name}...\n")
            self._all_output.flush()
            self._stop_requested = False

        worker = threading.Thread(
            target=self._run_command,
            args=(name, career_platform),
            daemon=True,
        )
        worker.start()
        return True

    def stop_command(self):
        with self._lock:
            if not self._state["running"] or self._state["stopping"]:
                return False
            self._stop_requested = True
            self._state["stopping"] = True
            process = self._process

        self._append_output("\n[dashboard] Stop requested.\n")
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
            except OSError as exc:
                if process.poll() is None:
                    with self._lock:
                        self._stop_requested = False
                        self._state["stopping"] = False
                    self._append_output(
                        f"[dashboard error] Could not stop command: {exc}\n"
                    )
                    return False
        return True

    def _append_output(self, text):
        with self._lock:
            self._all_output.write(text)
            self._all_output.flush()
            self._state["output"] = (self._state["output"] + text)[-MAX_OUTPUT_CHARS:]

    def _run_command(self, name, career_platform="search_all"):
        process = None
        try:
            child_env = os.environ.copy()
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env["PYTHONUTF8"] = "1"
            command = [
                sys.executable,
                "-u",
                str(MAIN_SCRIPT),
                COMMANDS[name],
            ]
            if name == "careers":
                command.extend(["--platform", career_platform])
            process = subprocess.Popen(
                command,
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
                stop_requested = self._stop_requested

            if stop_requested and process.poll() is None:
                process.terminate()
            if process.stdout is None:
                raise RuntimeError("Command output stream was not created.")

            for line in process.stdout:
                self._append_output(line)
            return_code = process.wait()
        except Exception as exc:
            self._append_output(f"\n[dashboard error] {exc}\n")
            return_code = process.returncode if process is not None else -1
        finally:
            if process is not None and process.stdout is not None:
                close_stdout = getattr(process.stdout, "close", None)
                if close_stdout is not None:
                    close_stdout()
            with self._lock:
                self._state["running"] = False
                self._state["stopping"] = False
                self._state["stopped"] = self._stop_requested and process is not None
                self._state["return_code"] = return_code
                self._process = None
                self._stop_requested = False


def _make_handler(controller):
    class DashboardHandler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type, headers=()):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            for name, value in headers:
                self.send_header(name, value)
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
            elif self.path == "/api/logs":
                command, output = controller.logs_for_export()
                if not output:
                    self._send(
                        404,
                        "No command logs are available to export.",
                        "text/plain; charset=utf-8",
                    )
                    return
                filename = f"job-bot-{command or 'logs'}-logs.txt"
                self._send(
                    200,
                    output,
                    "text/plain; charset=utf-8",
                    headers=(
                        ("Content-Disposition", f'attachment; filename="{filename}"'),
                    ),
                )
            else:
                self._send(404, "Not found.", "text/plain; charset=utf-8")

        def do_POST(self):
            if not self._valid_local_host() or not self._valid_origin():
                self._send(
                    403,
                    json.dumps({"error": "Local requests only."}),
                    "application/json; charset=utf-8",
                )
                return
            if self.path == "/api/stop":
                if not controller.stop_command():
                    self._send(
                        409,
                        json.dumps({"error": "No stoppable command is running."}),
                        "application/json; charset=utf-8",
                    )
                    return
                self._send(
                    202,
                    json.dumps({"stopping": True}),
                    "application/json; charset=utf-8",
                )
                return
            if self.path == "/api/career-sources":
                self._handle_career_source_import()
                return
            if self.path != "/api/run":
                self._send(
                    404,
                    json.dumps({"error": "Not found."}),
                    "application/json; charset=utf-8",
                )
                return
            if self.headers.get_content_type() != "application/json":
                self._send(
                    415,
                    json.dumps({"error": "Expected JSON request."}),
                    "application/json; charset=utf-8",
                )
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4096:
                    raise ValueError("Invalid request length.")
                payload = json.loads(self.rfile.read(length))
                name = payload.get("command") if isinstance(payload, dict) else None
                career_platform = (
                    payload.get("career_platform", "search_all")
                    if isinstance(payload, dict)
                    else "search_all"
                )
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(
                    400,
                    json.dumps({"error": str(exc)}),
                    "application/json; charset=utf-8",
                )
                return

            if not isinstance(name, str) or name not in COMMANDS:
                self._send(
                    400,
                    json.dumps({"error": "Unknown command."}),
                    "application/json; charset=utf-8",
                )
                return
            if name == "careers":
                if (
                    not isinstance(career_platform, str)
                    or career_platform not in {"search_all", "inhire"}
                ):
                    self._send(
                        400,
                        json.dumps({"error": "Unknown career platform."}),
                        "application/json; charset=utf-8",
                    )
                    return
                started = controller.start_command(
                    name,
                    career_platform=career_platform,
                )
            else:
                started = controller.start_command(name)
            if not started:
                self._send(
                    409,
                    json.dumps({"error": "A command is already running."}),
                    "application/json; charset=utf-8",
                )
                return
            self._send(
                202, json.dumps({"started": name}), "application/json; charset=utf-8"
            )

        def log_message(self, format, *args):
            if args and isinstance(args[0], int) and args[0] >= 400:
                super().log_message(format, *args)

        def _handle_career_source_import(self):
            if self.headers.get_content_type() != "application/json":
                self._send(
                    415,
                    json.dumps({"error": "Expected JSON request."}),
                    "application/json; charset=utf-8",
                )
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_CAREER_SOURCE_REQUEST_BYTES:
                    raise ValueError("Invalid request length.")
                payload = json.loads(self.rfile.read(length))
                sources = validate_career_source_payload(payload)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(
                    400,
                    json.dumps({"error": str(exc)}),
                    "application/json; charset=utf-8",
                )
                return

            try:
                inserted, skipped = insert_career_sources(sources)
            except sqlite3.Error as exc:
                self._send(
                    500,
                    json.dumps({"error": f"Could not save career sources: {exc}"}),
                    "application/json; charset=utf-8",
                )
                return

            self._send(
                200,
                json.dumps({"inserted": inserted, "skipped": skipped}),
                "application/json; charset=utf-8",
            )

    return DashboardHandler


def validate_career_source_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object.")

    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Provide at least one career source.")

    normalized_sources = []
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            raise ValueError(f"Source {index} must be a JSON object.")

        company = source.get("company")
        careers_url = source.get("careers_url")
        search_url = source.get("search_url")
        if not isinstance(company, str) or not company.strip():
            raise ValueError(f"Source {index} needs a company name.")
        if not isinstance(careers_url, str) or not careers_url.strip():
            raise ValueError(f"Source {index} needs a careers_url.")
        if search_url is not None and not isinstance(search_url, str):
            raise ValueError(f"Source {index} search_url must be a string or null.")

        careers_url = careers_url.strip()
        search_url = (
            search_url.strip()
            if isinstance(search_url, str) and search_url.strip()
            else None
        )
        for field_name, url in (
            ("careers_url", careers_url),
            ("search_url", search_url),
        ):
            if url:
                try:
                    parsed = urlsplit(url)
                except ValueError as exc:
                    raise ValueError(
                        f"Source {index} has an invalid {field_name}."
                    ) from exc
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError(
                        f"Source {index} {field_name} must be an HTTP or HTTPS URL."
                    )

        normalized_sources.append(
            {
                "company": company.strip(),
                "careers_url": careers_url,
                "search_url": search_url,
            }
        )

    return normalized_sources


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
        controller.close()
