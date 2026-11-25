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
    <article class="panel market-ai-panel" aria-labelledby="market-ai-title">
      <div class="market-ai-heading">
        <div>
          <p class="eyebrow">AI MARKET ANALYSIS · LOCAL OLLAMA</p>
          <h2 id="market-ai-title">Seniority, skills, and company demand</h2>
        </div>
        <strong id="market-ai-value">Waiting for analysis</strong>
      </div>
      <small id="market-ai-details">Analysis uses extracted data from the selected period.</small>
      <div id="market-ai-content" class="market-ai-content" aria-live="polite"></div>
    </article>
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
        <h2>Top skills by seniority level</h2>
        <p class="market-card-note">Percentages use postings with that stored level as the denominator.</p>
        <ol id="skills-by-level" class="market-list"><li class="empty">Loading...</li></ol>
      </article>
      <article class="panel market-list-panel">
        <h2>Top 5 companies by openings</h2>
        <p class="market-card-note">Company percentages use all postings; skill percentages use each company's postings.</p>
        <ol id="top-companies" class="market-list"><li class="empty">Loading...</li></ol>
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

    function renderSkillsByLevel(entries) {
      const list = document.getElementById("skills-by-level");
      list.replaceChildren();
      if (!entries.length) {
        const empty = document.createElement("li");
        empty.className = "empty";
        empty.textContent = "No seniority-level data available.";
        list.appendChild(empty);
        return;
      }

      for (const entry of entries) {
        const item = document.createElement("li");
        item.className = "market-list-item";
        const label = document.createElement("div");
        label.className = "market-list-label";
        const name = document.createElement("span");
        name.textContent = entry.name;
        const count = document.createElement("strong");
        count.textContent = entry.count.toLocaleString() + " postings";
        label.append(name, count);
        const skills = document.createElement("p");
        skills.className = "market-cross-skills";
        skills.textContent = entry.skills.length
          ? "Most common: " + entry.skills.map(skill =>
            `${skill.name} (${skill.percent}%)`
          ).join(", ")
          : "No extracted skills for these postings.";
        item.append(label, skills);
        list.appendChild(item);
      }
    }

    function renderTopCompanies(entries) {
      const list = document.getElementById("top-companies");
      list.replaceChildren();
      if (!entries.length) {
        const empty = document.createElement("li");
        empty.className = "empty";
        empty.textContent = "No company data available.";
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
        count.textContent = entry.count.toLocaleString() + " (" + entry.percent + "%)";
        label.append(name, count);
        const bar = document.createElement("div");
        bar.className = "market-bar";
        const fill = document.createElement("span");
        fill.style.width = (entry.count / maxCount * 100) + "%";
        bar.appendChild(fill);
        const skills = document.createElement("p");
        skills.className = "market-cross-skills";
        skills.textContent = entry.skills.length
          ? "Most common skills: " + entry.skills.map(skill =>
            `${skill.name} (${skill.percent}%)`
          ).join(", ")
          : "No skills extracted for these postings.";
        item.append(label, bar, skills);
        list.appendChild(item);
      }
    }

    function renderMarketAiAnalysis(analysis) {
      const value = document.getElementById("market-ai-value");
      const details = document.getElementById("market-ai-details");
      const content = document.getElementById("market-ai-content");
      content.replaceChildren();
      details.textContent = analysis.model
        ? analysis.model + " · local Ollama · qualitative sample analysis"
        : "Analysis uses extracted data from the selected period.";
      if (analysis.status !== "available") {
        value.textContent = "Unavailable";
        const message = document.createElement("p");
        message.className = "market-ai-commentary";
        message.textContent = analysis.reason || "Ollama did not return an analysis.";
        content.appendChild(message);
      } else {
        value.textContent = "Analysis ready";
        const label = document.createElement("strong");
        label.className = "market-ai-label";
        label.textContent = "AI commentary on the selected postings";
        const commentary = document.createElement("p");
        commentary.className = "market-ai-commentary";
        commentary.textContent = analysis.commentary;
        content.append(label, commentary);
      }
      if (analysis.data_limitations) {
        const limitations = document.createElement("p");
        limitations.className = "market-ai-limitations";
        limitations.textContent = "Data limitation: " + analysis.data_limitations;
        content.appendChild(limitations);
      }
    }

    function renderMarketAiLoading() {
      document.getElementById("market-ai-value").textContent = "AI is thinking…";
      document.getElementById("market-ai-details").textContent =
        "Local Ollama is cross-referencing the selected job data.";
      const content = document.getElementById("market-ai-content");
      content.replaceChildren();
      const loading = document.createElement("div");
      loading.className = "market-ai-loading";
      const spinner = document.createElement("span");
      spinner.className = "market-ai-spinner";
      spinner.setAttribute("role", "status");
      spinner.setAttribute("aria-label", "AI analysis in progress");
      const message = document.createElement("span");
      message.textContent = "Analyzing seniority, skills, and company demand…";
      loading.append(spinner, message);
      content.appendChild(loading);
    }

    async function loadJobsInfo() {
      const status = document.getElementById("jobs-info-status");
      status.textContent = "Loading job statistics...";
      status.className = "message";
      renderMarketAiLoading();
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
        renderSkillsByLevel(result.skills_by_level);
        renderTopCompanies(result.top_companies);
        renderMarketAiAnalysis(result.ai_market_analysis);
        status.textContent = result.jobs_with_skills.toLocaleString() +
          " postings collected " + periodLabel + " have extracted skills.";
      } catch (error) {
        status.textContent = error.message || "Could not load job statistics.";
        status.className = "message error";
        renderMarketAiAnalysis({
          status: "unavailable",
          reason: error.message || "Could not load job-market analysis.",
        });
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
