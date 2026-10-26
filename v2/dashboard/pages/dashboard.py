"""Dashboard page view."""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot v2.0 Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { margin: 0; background: #0b0f19; color: #e2e8f0; }
    header { background: #131b2e; border-bottom: 1px solid #1e293b; padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; gap: 24px; }
    header h1 { margin: 0; font-size: 20px; font-weight: 700; color: #60a5fa; }
    .tabs { display: flex; gap: 8px; }
    .tabs a { padding: 9px 14px; border-radius: 8px; color: #94a3b8; text-decoration: none; font-size: 14px; font-weight: 600; }
    .tabs a:hover, .tabs a.active { background: #1e293b; color: #f8fafc; }
    .badge { background: #1e293b; color: #94a3b8; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    .badge.ollama-online { background: #14532d; color: #bbf7d0; }
    .badge.ollama-offline { background: #7f1d1d; color: #fecaca; }
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
    button.warning { background: #b45309; }
    button.warning:hover:not(:disabled) { background: #d97706; }
    button.close-dashboard { background: #b91c1c; }
    button.close-dashboard:hover:not(:disabled) { background: #dc2626; }
    
    /* Terminal */
    .terminal-panel { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; height: calc(100vh - 220px); }
    .terminal-header { background: #0f172a; padding: 12px 18px; border-bottom: 1px solid #1e293b; display: flex; justify-content: space-between; align-items: center; }
    .terminal-header h3 { margin: 0; font-size: 14px; color: #94a3b8; }
    pre { margin: 0; padding: 18px; flex: 1; background: #080c14; color: #a5f3fc; font-family: "Cascadia Code", Consolas, monospace; font-size: 13px; line-height: 1.5; overflow: auto; white-space: pre-wrap; word-break: break-all; }
    
    .snackbar { position: fixed; left: 50%; bottom: 24px; z-index: 200; padding: 12px 20px; border-radius: 8px; color: #fff; font-size: 14px; box-shadow: 0 8px 24px rgba(0,0,0,0.35); opacity: 0; pointer-events: none; transform: translate(-50%, 12px); transition: opacity 0.2s ease, transform 0.2s ease; }
    .snackbar.show { opacity: 1; transform: translate(-50%, 0); }
    .snackbar.success { background: #15803d; }
    .snackbar.error { background: #b91c1c; }
    .snackbar.info { background: #334155; }
  </style>
</head>
<body>
  <header>
    <h1>Job-bot <span style="color:#94a3b8; font-weight:400;">Version 2.0</span></h1>
    <nav class="tabs" aria-label="Main navigation">
      <a class="active" href="/">Dashboard</a>
      <a href="/companies">Companies</a>
    </nav>
    <div style="display:flex; align-items:center; gap:12px;">
      <span id="ollama-status" class="badge ollama-offline" role="status" aria-live="polite">Ollama: checking</span>
      <button id="ollama-start" class="secondary" onclick="startOllama()">Start Ollama</button>
      <span id="run-status" class="badge">Idle</span>
      <button class="secondary" onclick="refreshStats()" style="padding:6px 12px; font-size:12px;">Refresh Stats</button>
      <button id="close-dashboard" class="close-dashboard" onclick="closeDashboard()">CLOSE</button>
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
          <button class="secondary" onclick="triggerCommand(['telegram', 'open'], 'Open first 10 in Chrome')">4. Open first 10</button>
          <button class="secondary" onclick="triggerCommand(['telegram', 'open'], 'Continue Telegram review')">Continue (next 10)</button>
          <button class="secondary" disabled title="Coming soon">Connect to Recruiters</button>
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
          <label style="font-size:14px; color:#cbd5e1; cursor:pointer;">
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
        <div style="display:flex; gap:8px;">
          <button class="secondary" style="padding:4px 10px; font-size:12px;" onclick="copyLogs()">Copy</button>
          <button id="btn-stop" class="danger" style="padding:4px 10px; font-size:12px;" onclick="stopCommand()" disabled>Stop</button>
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
      document.getElementById("run-status").style.background = "#2563eb";
      document.getElementById("run-status").style.color = "#ffffff";

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
          statusEl.style.background = "#2563eb";
          statusEl.style.color = "#ffffff";
        } else {
          statusEl.textContent = "Idle";
          statusEl.style.background = "#1e293b";
          statusEl.style.color = "#94a3b8";
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
