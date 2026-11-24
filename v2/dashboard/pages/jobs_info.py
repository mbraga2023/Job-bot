"""Job-market statistics page."""

from v2.dashboard.components.header import render_header

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot v2.0 Jobs Info</title>
  <link rel="stylesheet" href="/style/dashboard.css">
</head>
<body class="jobs-info-page">
  <!-- SHARED_HEADER -->
  <main>
    <section class="market-intro">
      <div>
        <p class="eyebrow">JOB MARKET · YOUR DATABASE</p>
        <h2>Jobs Info</h2>
        <p>Explore the roles, skills, work arrangements, and levels represented in collected job postings.</p>
      </div>
      <div class="market-controls">
        <label for="period-filter">Period
          <select id="period-filter">
            <option value="30" selected>Last 30 days</option>
            <option value="all">All time</option>
          </select>
        </label>
        <button id="refresh-jobs-info" class="secondary" type="button">Refresh</button>
      </div>
    </section>
    <p id="jobs-info-status" class="message" role="status" aria-live="polite">Loading job statistics...</p>
    <section class="market-kpis" aria-label="Job market summary">
      <article class="stat-card"><div class="label">Job postings</div><div id="total-jobs" class="value">—</div></article>
      <article class="stat-card"><div class="label">Remote positions</div><div id="remote-jobs" class="value">—</div><small id="remote-percent"></small></article>
      <article class="stat-card"><div class="label">Different job titles</div><div id="titles-count" class="value">—</div></article>
      <article class="stat-card"><div class="label">Skills found</div><div id="skills-count" class="value">—</div></article>
    </section>
    <p id="market-scope-note" class="market-note">Statistics use jobs first collected in the selected period.</p>
    <section class="market-grid">
      <article class="panel market-list-panel">
        <h2>Top 10 most wanted skills</h2>
        <p id="skills-denominator" class="market-card-note">Share of postings with extracted skills.</p>
        <ol id="top-skills" class="market-list"><li class="empty">Loading...</li></ol>
      </article>
      <article class="panel market-list-panel">
        <h2>Top 5 most common job titles</h2>
        <ol id="top-titles" class="market-list"><li class="empty">Loading...</li></ol>
      </article>
      <article class="panel market-list-panel">
        <h2>Positions by level</h2>
        <ol id="levels" class="market-list"><li class="empty">Loading...</li></ol>
      </article>
      <article class="panel market-list-panel">
        <h2>Positions by contract</h2>
        <ol id="contracts" class="market-list"><li class="empty">Loading...</li></ol>
      </article>
    </section>
  </main>
  <script>
    function renderRankedList(elementId, entries) {
      const list = document.getElementById(elementId);
      list.replaceChildren();
      if (!entries.length) {
        const empty = document.createElement("li");
        empty.className = "empty";
        empty.textContent = "No data available yet.";
        list.appendChild(empty);
        return;
      }

      const maxCount = entries[0].count;
      for (const entry of entries) {
        const item = document.createElement("li");
        item.className = "market-list-item";
        const label = document.createElement("div");
        label.className = "market-list-label";
        const name = document.createElement("span");
        name.textContent = entry.name;
        const count = document.createElement("strong");
        count.textContent = entry.percent === undefined
          ? entry.count.toLocaleString()
          : entry.count.toLocaleString() + " (" + entry.percent + "%)";
        label.append(name, count);
        const bar = document.createElement("div");
        bar.className = "market-bar";
        const fill = document.createElement("span");
        fill.style.width = (entry.count / maxCount * 100) + "%";
        bar.appendChild(fill);
        item.append(label, bar);
        list.appendChild(item);
      }
    }

    async function loadJobsInfo() {
      const status = document.getElementById("jobs-info-status");
      status.textContent = "Loading job statistics...";
      status.className = "message";
      try {
        const period = document.getElementById("period-filter").value;
        const response = await fetch("/api/jobs-info?period=" + encodeURIComponent(period));
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not load job statistics.");
        const periodLabel = result.period_days === null ? "at any time" : "in the last 30 days";
        document.getElementById("market-scope-note").textContent =
          "Statistics use jobs first collected " + periodLabel +
          ". Skill and level details are shown where they were extracted.";
        document.getElementById("total-jobs").textContent = result.total_jobs.toLocaleString();
        document.getElementById("remote-jobs").textContent = result.remote_jobs.toLocaleString();
        document.getElementById("remote-percent").textContent =
          result.remote_percent + "% of " + result.total_jobs.toLocaleString() + " postings";
        document.getElementById("titles-count").textContent = result.titles_count.toLocaleString();
        document.getElementById("skills-count").textContent = result.skills_count.toLocaleString();
        document.getElementById("skills-denominator").textContent =
          "Share of " + result.total_jobs.toLocaleString() + " postings in this period.";
        renderRankedList("top-skills", result.top_skills);
        renderRankedList("top-titles", result.top_titles);
        renderRankedList("levels", result.levels);
        renderRankedList("contracts", result.contracts);
        status.textContent = result.jobs_with_skills.toLocaleString() +
          " postings collected " + periodLabel + " have extracted skills.";
      } catch (error) {
        status.textContent = error.message || "Could not load job statistics.";
        status.className = "message error";
      }
    }

    document.getElementById("refresh-jobs-info").addEventListener("click", loadJobsInfo);
    document.getElementById("period-filter").addEventListener("change", loadJobsInfo);
    loadJobsInfo();
  </script>
</body>
</html>
"""

PAGE_HTML = PAGE_HTML.replace("<!-- SHARED_HEADER -->", render_header("jobs-info"))
