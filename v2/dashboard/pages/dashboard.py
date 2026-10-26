"""Dashboard page view."""

from v2.dashboard.components.header import render_header

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot v2.0 Dashboard</title>
  <link rel="stylesheet" href="/style/dashboard.css">
</head>
<body class="dashboard-page">
  <!-- SHARED_HEADER -->

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
          <button class="secondary" onclick="triggerCommand(['telegram', 'open'], 'Open first 10 in Chrome')">4. Open first 10</button>
          <button class="secondary" onclick="triggerCommand(['telegram', 'open'], 'Continue Telegram review')">Continue (next 10)</button>
          <button class="secondary" disabled title="Coming soon">Connect to Recruiters</button>
        </div>
      </div>

      <!-- Flow 2 -->
      <div class="flow-card">
        <h2>🌐 Flow 2: Company Career Pages</h2>
        <div class="platform-options">
          <label class="platform-option">
            <input type="radio" name="career-platform" value="search_all" checked> Search All
          </label>
          <label class="platform-option">
            <input type="radio" name="career-platform" value="inhire"> InHire Only
          </label>
          <label class="platform-option">
            <input type="radio" name="career-platform" value="gupy"> Gupy Only
          </label>
        </div>
        <div class="actions-grid">
          <button onclick="scanCareers()">1. Scan Pages</button>
          <button onclick="triggerCommand(['careers', 'validate'], 'Careers Validate')">2. Validate (AI)</button>
          <button class="secondary" onclick="triggerCommand(['careers', 'open'], 'Open first 10 in Chrome')">3. Open first 10</button>
          <button class="secondary" onclick="triggerCommand(['careers', 'open'], 'Continue career review')">Continue (next 10)</button>
        </div>
      </div>

      <!-- System Operations -->
      <div class="flow-card">
        <h2>⚙️ Operations & Database</h2>
        <div class="actions-grid">
          <button class="secondary" onclick="triggerCommand(['migrate'], 'Migrate from v1')">Migrate from v1</button>
          <button class="secondary" onclick="triggerCommand(['stats'], 'Print Stats')">Log Stats</button>
          <button class="warning" onclick="cleanNonQaJobs()">Temporary: Clean non-QA jobs</button>
        </div>
      </div>
    </section>

    <!-- Terminal -->
    <section class="terminal-panel">
      <div class="terminal-header">
        <h3>Live Command Output</h3>
        <div class="terminal-actions">
          <button class="secondary button-small" onclick="copyLogs()">Copy</button>
          <button id="btn-stop" class="danger button-small" onclick="stopCommand()" disabled>Stop</button>
        </div>
      </div>
      <pre id="terminal-output">Ready. Select a workflow stage to begin.</pre>
    </section>
  </main>

  <div id="snackbar" class="snackbar" role="status" aria-live="polite"></div>

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

    async function refreshOllamaStatus() {
      const status = document.getElementById("ollama-status");
      const button = document.getElementById("ollama-start");
      try {
        const response = await fetch("/api/ollama/status");
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Ollama status unavailable.");
        status.textContent = result.running ? "Ollama: Online" : "Ollama: Offline";
        status.className = "badge " + (result.running ? "ollama-online" : "ollama-offline");
        button.disabled = result.running;
      } catch (error) {
        status.textContent = "Ollama: Status unavailable";
        status.className = "badge ollama-offline";
        button.disabled = false;
      }
    }

    async function startOllama() {
      const button = document.getElementById("ollama-start");
      button.disabled = true;
      button.textContent = "Starting...";
      try {
        const response = await fetch("/api/ollama/start", { method: "POST" });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not start Ollama.");
        showSnackbar(
          result.started ? "Ollama is starting." : "Ollama is already online.",
          "success"
        );
      } catch (error) {
        showSnackbar(error.message || "Could not start Ollama.", "error");
      } finally {
        button.textContent = "Start Ollama";
        refreshOllamaStatus();
      }
    }

    async function closeDashboard() {
      if (!window.confirm("Close the dashboard and stop the Ollama service on port 11434?")) return;

      const button = document.getElementById("close-dashboard");
      button.disabled = true;
      try {
        const response = await fetch("/api/close", { method: "POST" });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not close the dashboard.");

        document.body.innerHTML = "<main><h2>Dashboard stopped. You can close this tab.</h2></main>";
        window.close();
      } catch (error) {
        button.disabled = false;
        showSnackbar(error.message || "Could not close the dashboard.", "error");
      }
    }

    let commandNeedsStatsRefresh = false;

    async function triggerCommand(args, label) {
      document.getElementById("terminal-output").textContent = ">> Starting " + label + "...\\n";
      document.getElementById("btn-stop").disabled = false;
      document.getElementById("run-status").textContent = "Running";
      document.getElementById("run-status").className = "badge running";

      try {
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ args, label })
        });
        const result = await response.json();
        if (!response.ok || !result.started) {
          throw new Error(result.error || "Could not start command.");
        }
        commandNeedsStatsRefresh = true;
      } catch (error) {
        showSnackbar(error.message || "Could not start command.", "error");
      }
    }

    function scanCareers() {
      const selectedPlatform = document.querySelector('input[name="career-platform"]:checked').value;
      triggerCommand(["careers", "scan", "--platform", selectedPlatform], "Career Scan (" + selectedPlatform + ")");
    }

    async function stopCommand() {
      await fetch("/api/stop", { method: "POST" });
    }

    async function cleanNonQaJobs() {
      try {
        const previewResponse = await fetch("/api/non-qa-jobs");
        const preview = await previewResponse.json();
        if (!previewResponse.ok) throw new Error(preview.error || "Could not count jobs.");
        if (preview.count === 0) {
          alert("No non-QA jobs found.");
          return;
        }

        const confirmation = prompt(
          `This will permanently delete ${preview.count} jobs whose titles are not recognized as QA, including jobs with missing titles. Type DELETE NON-QA JOBS to continue.`
        );
        if (confirmation !== "DELETE NON-QA JOBS") return;

        const response = await fetch("/api/non-qa-jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_count: preview.count, confirmation })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not delete jobs.");
        alert(`Deleted ${result.deleted} non-QA jobs.`);
        refreshStats();
      } catch (error) {
        alert("Cleanup failed: " + error.message);
      }
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
          statusEl.className = "badge running";
        } else {
          statusEl.textContent = "Idle";
          statusEl.className = "badge";
          if (commandNeedsStatsRefresh) {
            commandNeedsStatsRefresh = false;
            await refreshStats();
          }
        }
      } catch (e) {}
    }

    function copyLogs() {
      navigator.clipboard.writeText(document.getElementById("terminal-output").textContent);
    }

    let snackbarTimeout;
    function showSnackbar(message, type = "info") {
      const snackbar = document.getElementById("snackbar");
      snackbar.textContent = message;
      snackbar.className = "snackbar " + type + " show";
      clearTimeout(snackbarTimeout);
      snackbarTimeout = setTimeout(() => {
        snackbar.classList.remove("show");
      }, 3500);
    }

    setInterval(pollLogs, 1000);
    setInterval(refreshOllamaStatus, 5000);
    refreshOllamaStatus();
    refreshStats();
  </script>
</body>
</html>
"""

PAGE_HTML = PAGE_HTML.replace(
    "<!-- SHARED_HEADER -->",
    render_header(
        "dashboard",
        """<span id="ollama-status" class="badge ollama-offline" role="status" aria-live="polite">Ollama: checking</span>
    <button id="ollama-start" class="secondary" onclick="startOllama()">Start Ollama</button>
    <span id="run-status" class="badge">Idle</span>
    <button class="secondary button-refresh" onclick="refreshStats()">Refresh Stats</button>
    <button id="close-dashboard" class="close-dashboard" onclick="closeDashboard()">CLOSE</button>""",
    ),
)
