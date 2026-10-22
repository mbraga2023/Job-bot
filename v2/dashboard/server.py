"""Embedded Web Dashboard Server for Job-bot Version 2.0."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from v2.core.database import get_database_stats, insert_career_source

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SCRIPT = PROJECT_ROOT / "v2" / "main.py"
HOST = "127.0.0.1"
DEFAULT_PORT = 8766
MAX_OUTPUT_CHARS = 100_000

# Process state
ACTIVE_PROCESS: subprocess.Popen | None = None
ACTIVE_PROCESS_LOCK = threading.Lock()
COMMAND_OUTPUT: list[str] = []
COMMAND_OUTPUT_LOCK = threading.Lock()
CURRENT_COMMAND: str | None = None


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


PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot v2.0 Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { margin: 0; background: #0b0f19; color: #e2e8f0; }
    header { background: #131b2e; border-bottom: 1px solid #1e293b; padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; }
    header h1 { margin: 0; font-size: 20px; font-weight: 700; color: #60a5fa; }
    .badge { background: #1e293b; color: #94a3b8; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    main { max-width: 1400px; margin: 32px auto; padding: 0 24px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); gap: 32px; }
    
    /* Stats Bar */
    .stats-container { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 8px; }
    .stat-card { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 18px 24px; }
    .stat-card .label { font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-card .value { font-size: 28px; font-weight: 700; margin-top: 6px; color: #f8fafc; }
    
    /* Flow Cards */
    .flow-card { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
    .flow-card h2 { margin: 0 0 16px 0; font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
    .actions-grid { display: flex; flex-wrap: wrap; gap: 12px; }
    
    button { border: 0; border-radius: 8px; padding: 10px 18px; background: #2563eb; color: white; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.15s ease; }
    button:hover:not(:disabled) { background: #3b82f6; transform: translateY(-1px); }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    button.secondary { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; }
    button.secondary:hover:not(:disabled) { background: #334155; }
    button.danger { background: #dc2626; }
    button.danger:hover:not(:disabled) { background: #ef4444; }
    
    /* Terminal */
    .terminal-panel { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; height: calc(100vh - 220px); }
    .terminal-header { background: #0f172a; padding: 12px 18px; border-bottom: 1px solid #1e293b; display: flex; justify-content: space-between; align-items: center; }
    .terminal-header h3 { margin: 0; font-size: 14px; color: #94a3b8; }
    pre { margin: 0; padding: 18px; flex: 1; background: #080c14; color: #a5f3fc; font-family: "Cascadia Code", Consolas, monospace; font-size: 13px; line-height: 1.5; overflow: auto; white-space: pre-wrap; word-break: break-all; }
    
    /* Modal */
    .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100; align-items: center; justify-content: center; }
    .modal-overlay.open { display: flex; }
    .modal-box { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; width: 480px; padding: 24px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
    .modal-box h3 { margin-top: 0; font-size: 18px; }
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 6px; }
    .form-group input { width: 100%; box-sizing: border-box; background: #0b0f19; border: 1px solid #334155; border-radius: 6px; padding: 10px; color: #f8fafc; font-size: 14px; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
  </style>
</head>
<body>
  <header>
    <h1>Job-bot <span style="color:#94a3b8; font-weight:400;">Version 2.0</span></h1>
    <div style="display:flex; align-items:center; gap:12px;">
      <span id="run-status" class="badge">Idle</span>
      <button class="secondary" onclick="refreshStats()" style="padding:6px 12px; font-size:12px;">Refresh Stats</button>
    </div>
  </header>

  <main>
    <div class="stats-container">
      <div class="stat-card">
        <div class="label">Career Sources</div>
        <div id="stat-sources" class="value">0</div>
      </div>
      <div class="stat-card">
        <div class="label">Total Jobs</div>
        <div id="stat-jobs" class="value">0</div>
      </div>
      <div class="stat-card">
        <div class="label">Validated / Open</div>
        <div id="stat-open" class="value">0</div>
      </div>
      <div class="stat-card">
        <div class="label">Manual Review</div>
        <div id="stat-manual" class="value">0</div>
      </div>
    </div>

    <section class="controls-column">
      <!-- Flow 1 -->
      <div class="flow-card">
        <h2>⚡ Flow 1: Telegram & LinkedIn</h2>
        <div class="actions-grid">
          <button onclick="triggerCommand(['telegram', 'collect'], 'Telegram Collect')">1. Collect</button>
          <button onclick="triggerCommand(['telegram', 'validate'], 'Telegram Validate')">2. Validate</button>
          <button onclick="triggerCommand(['telegram', 'linkedin'], 'LinkedIn Check')">3. LinkedIn</button>
          <button class="secondary" onclick="triggerCommand(['telegram', 'open'], 'Open in Chrome')">4. Open in Chrome</button>
        </div>
      </div>

      <!-- Flow 2 -->
      <div class="flow-card">
        <h2>🌐 Flow 2: Company Career Pages</h2>
        <div style="margin-bottom:14px; display:flex; gap:16px;">
          <label style="font-size:14px; color:#cbd5e1; cursor:pointer;">
            <input type="radio" name="career-platform" value="search_all" checked> Search All
          </label>
          <label style="font-size:14px; color:#cbd5e1; cursor:pointer;">
            <input type="radio" name="career-platform" value="inhire"> InHire Only
          </label>
        </div>
        <div class="actions-grid">
          <button onclick="scanCareers()">1. Scan Pages</button>
          <button onclick="triggerCommand(['careers', 'validate'], 'Careers Validate')">2. Validate (AI)</button>
          <button class="secondary" onclick="triggerCommand(['careers', 'open'], 'Open in Chrome')">3. Open in Chrome</button>
          <button class="secondary" onclick="openImportModal()">+ Add Source</button>
        </div>
      </div>

      <!-- System Operations -->
      <div class="flow-card">
        <h2>⚙️ Operations & Database</h2>
        <div class="actions-grid">
          <button class="secondary" onclick="triggerCommand(['migrate'], 'Migrate from v1')">Migrate from v1</button>
          <button class="secondary" onclick="triggerCommand(['stats'], 'Print Stats')">Log Stats</button>
        </div>
      </div>
    </section>

    <!-- Terminal -->
    <section class="terminal-panel">
      <div class="terminal-header">
        <h3>Live Command Output</h3>
        <div style="display:flex; gap:8px;">
          <button class="secondary" style="padding:4px 10px; font-size:12px;" onclick="copyLogs()">Copy</button>
          <button id="btn-stop" class="danger" style="padding:4px 10px; font-size:12px;" onclick="stopCommand()" disabled>Stop</button>
        </div>
      </div>
      <pre id="terminal-output">Ready. Select a workflow stage to begin.</pre>
    </section>
  </main>

  <!-- Add Source Modal -->
  <div id="import-modal" class="modal-overlay">
    <div class="modal-box">
      <h3>Add Career Source</h3>
      <form id="add-source-form" onsubmit="submitSource(event)">
        <div class="form-group">
          <label>Company Name</label>
          <input name="company" required placeholder="e.g. Nubank">
        </div>
        <div class="form-group">
          <label>Careers URL</label>
          <input name="careers_url" type="url" required placeholder="https://company.careers.com">
        </div>
        <div class="form-group">
          <label>Search URL (Optional)</label>
          <input name="search_url" type="url" placeholder="https://company.careers.com/search?q=qa">
        </div>
        <div class="modal-actions">
          <button type="button" class="secondary" onclick="closeImportModal()">Cancel</button>
          <button type="submit">Save Source</button>
        </div>
      </form>
    </div>
  </div>

  <script>
    async function refreshStats() {
      try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        document.getElementById("stat-sources").textContent = data.career_sources_active || 0;
        document.getElementById("stat-jobs").textContent = data.jobs_total || 0;
        
        const openCnt = (data.jobs_by_status.OPEN || 0) + (data.jobs_by_status.VALIDATED || 0);
        document.getElementById("stat-open").textContent = openCnt;
        document.getElementById("stat-manual").textContent = data.jobs_by_status.MANUAL || 0;
      } catch (e) {
        console.error("Failed to load stats", e);
      }
    }

    async function triggerCommand(args, label) {
      document.getElementById("terminal-output").textContent = ">> Starting " + label + "...\\n";
      document.getElementById("btn-stop").disabled = false;
      document.getElementById("run-status").textContent = "Running";
      document.getElementById("run-status").style.background = "#2563eb";
      document.getElementById("run-status").style.color = "#ffffff";

      await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ args, label })
      });
    }

    function scanCareers() {
      const selectedPlatform = document.querySelector('input[name="career-platform"]:checked').value;
      triggerCommand(["careers", "scan", "--platform", selectedPlatform], "Career Scan (" + selectedPlatform + ")");
    }

    async function stopCommand() {
      await fetch("/api/stop", { method: "POST" });
    }

    async function pollLogs() {
      try {
        const res = await fetch("/api/logs");
        const data = await res.json();
        const pre = document.getElementById("terminal-output");
        if (data.logs) {
          pre.textContent = data.logs;
          pre.scrollTop = pre.scrollHeight;
        }
        document.getElementById("btn-stop").disabled = !data.running;
        const statusEl = document.getElementById("run-status");
        if (data.running) {
          statusEl.textContent = "Running: " + (data.command || "");
          statusEl.style.background = "#2563eb";
          statusEl.style.color = "#ffffff";
        } else {
          statusEl.textContent = "Idle";
          statusEl.style.background = "#1e293b";
          statusEl.style.color = "#94a3b8";
        }
      } catch (e) {}
    }

    function copyLogs() {
      navigator.clipboard.writeText(document.getElementById("terminal-output").textContent);
    }

    function openImportModal() { document.getElementById("import-modal").classList.add("open"); }
    function closeImportModal() { document.getElementById("import-modal").classList.remove("open"); }

    async function submitSource(e) {
      e.preventDefault();
      const form = e.target;
      const payload = {
        company: form.company.value,
        careers_url: form.careers_url.value,
        search_url: form.search_url.value
      };
      await fetch("/api/import-career", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      closeImportModal();
      form.reset();
      refreshStats();
    }

    setInterval(pollLogs, 1000);
    refreshStats();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for local web UI and JSON endpoints."""

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

        if parsed.path == "/api/stats":
            stats = get_database_stats()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode("utf-8"))
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

        if parsed.path == "/api/import-career":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            company = data.get("company", "").strip()
            careers_url = data.get("careers_url", "").strip()
            search_url = data.get("search_url", "").strip() or None

            if company and careers_url:
                insert_career_source(company, careers_url, search_url)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


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
        httpd.server_close()
