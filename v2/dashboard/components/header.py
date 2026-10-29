"""Shared dashboard page header."""

from typing import Literal


def render_header(
    active_page: Literal["dashboard", "companies", "test-insights"],
) -> str:
    """Render the shared title, navigation, and dashboard controls."""
    dashboard_link = (
        '<a href="/" class="active" aria-current="page">Dashboard</a>'
        if active_page == "dashboard"
        else '<a href="/">Dashboard</a>'
    )
    companies_link = (
        '<a href="/companies" class="active" aria-current="page">Companies</a>'
        if active_page == "companies"
        else '<a href="/companies">Companies</a>'
    )
    test_insights_link = (
        '<a href="/test-insights" class="active" aria-current="page">Test Insights</a>'
        if active_page == "test-insights"
        else '<a href="/test-insights">Test Insights</a>'
    )
    return f"""<header class="site-header">
    <h1>Job-bot <span>Version 2.0</span></h1>
    <nav class="tabs" aria-label="Main navigation">
      {dashboard_link}
      {companies_link}
      {test_insights_link}
    </nav>
    <div class="header-actions">
      <span id="ollama-status" class="badge ollama-offline" role="status" aria-live="polite">Ollama API: checking</span>
      <button id="ollama-start" class="secondary" onclick="window.startDashboardOllama()">Start Ollama</button>
      <span id="run-status" class="badge">Idle</span>
      <button class="secondary button-refresh" onclick="window.refreshDashboardStats()">Refresh Stats</button>
      <button id="close-dashboard" class="close-dashboard" onclick="window.closeDashboard()">CLOSE</button>
    </div>
  </header>
  <div id="snackbar" class="snackbar" role="status" aria-live="polite"></div>
  <script>
    window.showDashboardMessage = function(message, type = "info") {{
      const snackbar = document.getElementById("snackbar");
      snackbar.textContent = message;
      snackbar.className = "snackbar " + type + " show";
      clearTimeout(window.dashboardSnackbarTimeout);
      window.dashboardSnackbarTimeout = setTimeout(() => snackbar.classList.remove("show"), 3500);
    }};

    window.refreshDashboardStats = async function() {{
      if (typeof window.refreshStats === "function") {{
        await window.refreshStats();
        return;
      }}
      try {{
        const response = await fetch("/api/stats");
        const stats = await response.json();
        if (!response.ok) throw new Error(stats.error || "Could not refresh stats.");
        window.showDashboardMessage(
          `Active companies: ${{stats.career_sources_active || 0}} | Jobs: ${{stats.jobs_total || 0}}`,
          "info"
        );
      }} catch (error) {{
        window.showDashboardMessage(error.message || "Could not refresh stats.", "error");
      }}
    }};

    window.refreshDashboardOllamaStatus = async function() {{
      const status = document.getElementById("ollama-status");
      const button = document.getElementById("ollama-start");
      try {{
        const response = await fetch("/api/ollama/status");
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Ollama status unavailable.");
        status.textContent = result.running ? "Ollama API: Online" : "Ollama API: Offline";
        if (!result.python_client_available) {{
          status.textContent += " | Python client missing";
        }}
        const ollamaReady = result.running && result.python_client_available;
        status.className = "badge " + (ollamaReady ? "ollama-online" : "ollama-offline");
        status.title = result.python_client_available
          ? ""
          : "Install dependencies with .venv/Scripts/python.exe -m pip install -r requirements.txt";
        button.disabled = result.running;
      }} catch (error) {{
        status.textContent = "Ollama API: Status unavailable";
        status.className = "badge ollama-offline";
        button.disabled = false;
      }}
    }};

    window.startDashboardOllama = async function() {{
      const button = document.getElementById("ollama-start");
      button.disabled = true;
      button.textContent = "Starting...";
      try {{
        const response = await fetch("/api/ollama/start", {{ method: "POST" }});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not start Ollama.");
        window.showDashboardMessage(
          result.started ? "Ollama is starting." : "Ollama is already online.",
          "success"
        );
      }} catch (error) {{
        window.showDashboardMessage(error.message || "Could not start Ollama.", "error");
      }} finally {{
        button.textContent = "Start Ollama";
        window.refreshDashboardOllamaStatus();
      }}
    }};

    window.closeDashboard = async function() {{
      if (!window.confirm("Close the dashboard and stop the Ollama service on port 11434?")) return;
      const button = document.getElementById("close-dashboard");
      button.disabled = true;
      try {{
        const response = await fetch("/api/close", {{ method: "POST" }});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not close the dashboard.");
        document.body.innerHTML = "<main><h2>Dashboard stopped. You can close this tab.</h2></main>";
        window.close();
      }} catch (error) {{
        button.disabled = false;
        window.showDashboardMessage(error.message || "Could not close the dashboard.", "error");
      }}
    }};

    window.refreshDashboardOllamaStatus();
    setInterval(window.refreshDashboardOllamaStatus, 5000);
  </script>"""
