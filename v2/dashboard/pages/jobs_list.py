"""Paginated job-list dashboard page."""

from v2.dashboard.components.header import render_header

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot v2.0 Jobs List</title>
  <link rel="stylesheet" href="/style/dashboard.css">
</head>
<body class="jobs-list-page">
  <!-- SHARED_HEADER -->
  <main>
    <section class="jobs-list-intro">
      <div>
        <p class="eyebrow">JOB POSTINGS · YOUR DATABASE</p>
        <h2>Jobs List</h2>
        <p>Browse the 50 most recently collected jobs per page or search all stored postings.</p>
      </div>
    </section>
    <form id="jobs-search-form" class="jobs-search">
      <label for="jobs-search-input">Search jobs</label>
      <input
        id="jobs-search-input"
        name="q"
        type="search"
        maxlength="200"
        placeholder="Title, company, location, skill, status…"
        autocomplete="off"
      >
      <button id="jobs-search-button" class="secondary" type="submit">Search</button>
    </form>
    <p id="jobs-list-status" class="message" role="status" aria-live="polite">Loading jobs…</p>
    <div class="jobs-table-wrap">
      <table class="jobs-table">
        <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Company</th>
            <th scope="col">Level</th>
            <th scope="col">Location</th>
            <th scope="col">Remote</th>
            <th scope="col">Status</th>
            <th scope="col">Added to DB</th>
            <th scope="col">Open</th>
            <th scope="col">Details</th>
          </tr>
        </thead>
        <tbody id="jobs-table-body">
          <tr><td class="empty" colspan="9">Loading jobs…</td></tr>
        </tbody>
      </table>
    </div>
    <nav class="jobs-pagination" aria-label="Job list pagination">
      <button id="jobs-previous-page" class="secondary" type="button" disabled>Previous</button>
      <span id="jobs-page-status" role="status" aria-live="polite">Page 1 of 1</span>
      <button id="jobs-next-page" class="secondary" type="button" disabled>Next</button>
    </nav>
    <dialog id="job-details-dialog" class="job-details-dialog" aria-labelledby="job-details-title">
      <div class="job-details-heading">
        <div>
          <p class="eyebrow">POSTING DETAILS</p>
          <h2 id="job-details-title">Job details</h2>
        </div>
        <button id="close-job-details" class="secondary" type="button">Close</button>
      </div>
      <div id="job-details-content" class="job-details-content"></div>
    </dialog>
  </main>
  <script>
    const jobsTableBody = document.getElementById("jobs-table-body");
    const jobsListStatus = document.getElementById("jobs-list-status");
    const jobsSearchInput = document.getElementById("jobs-search-input");
    const jobsPreviousPage = document.getElementById("jobs-previous-page");
    const jobsNextPage = document.getElementById("jobs-next-page");
    const jobsPageStatus = document.getElementById("jobs-page-status");
    const jobDetailsDialog = document.getElementById("job-details-dialog");
    let searchTimer;
    let activeSearch = 0;
    let currentPage = 1;

    function addJobCell(row, value, className = "") {
      const cell = document.createElement("td");
      if (className) cell.className = className;
      cell.textContent = value || "—";
      row.appendChild(cell);
      return cell;
    }

    function formatJobValue(value) {
      if (value === null || value === undefined || value === "") return "—";
      if (Array.isArray(value)) return value.join(", ") || "—";
      if (typeof value !== "string") return JSON.stringify(value);
      try {
        const parsed = JSON.parse(value);
        if (Array.isArray(parsed)) return parsed.join(", ") || "—";
        if (parsed && typeof parsed === "object") return JSON.stringify(parsed, null, 2);
      } catch {
        return value;
      }
      return value;
    }

    function createExternalLink(value, text, className = "") {
      if (typeof value !== "string" || !/^https?:\\/\\//i.test(value)) return null;
      const link = document.createElement("a");
      link.href = value;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = text;
      if (className) link.className = className;
      return link;
    }

    function addJobDetail(label, value, url = false) {
      const item = document.createElement("div");
      item.className = "job-detail";
      const name = document.createElement("strong");
      name.textContent = label;
      const content = document.createElement("div");
      content.className = "job-detail-value";
      const formatted = formatJobValue(value);
      if (url) {
        const link = createExternalLink(formatted, formatted);
        if (link) {
          content.appendChild(link);
        } else {
          content.textContent = formatted;
        }
      } else {
        content.textContent = formatted;
      }
      item.append(name, content);
      document.getElementById("job-details-content").appendChild(item);
    }

    function showJobDetails(job) {
      document.getElementById("job-details-title").textContent =
        job.title || "Job details";
      const content = document.getElementById("job-details-content");
      content.replaceChildren();
      const fields = [
        ["Job ID", job.id],
        ["Company", job.company],
        ["Pipeline", job.pipeline],
        ["External ID", job.external_id],
        ["Career source ID", job.career_source_id],
        ["Location", job.location],
        ["Remote", job.remote === null ? null : job.remote ? "Yes" : "No"],
        ["Seniority level", job.level],
        ["Contract", job.contract],
        ["Category", job.category],
        ["Status", job.status],
        ["Discard reason", job.discard_reason],
        ["AI status", job.ai_status],
        ["AI reason", job.ai_reason],
        ["Technologies / skills", job.technologies],
        ["Requirements", job.requirements],
        ["Differentials", job.differentials],
        ["Benefits", job.benefits],
        ["Description", job.description],
        ["Application source", job.application_source],
        ["Application URL", job.application_url, true],
        ["Source URL", job.source_url, true],
        ["Published date", job.published_date],
        ["Added to database", job.first_seen_at],
        ["Last seen", job.last_seen_at],
        ["Validated at", job.validated_at],
        ["Updated at", job.updated_at],
      ];
      for (const [label, value, isUrl] of fields) {
        addJobDetail(label, value, isUrl);
      }
      jobDetailsDialog.showModal();
    }

    function renderJobs(jobs) {
      jobsTableBody.replaceChildren();
      if (!jobs.length) {
        const row = document.createElement("tr");
        const cell = addJobCell(row, "No matching jobs found.", "empty");
        cell.colSpan = 9;
        jobsTableBody.appendChild(row);
        return;
      }

      for (const job of jobs) {
        const row = document.createElement("tr");
        addJobCell(row, job.title, "job-title-cell");
        addJobCell(row, job.company);
        addJobCell(row, job.level);
        addJobCell(row, job.location);
        addJobCell(row, job.remote ? "Yes" : "No");
        addJobCell(row, job.status);
        addJobCell(row, job.first_seen_at);
        const openCell = document.createElement("td");
        const openLink = createExternalLink(job.source_url, "Open", "job-open-button");
        if (openLink) {
          openCell.appendChild(openLink);
        } else {
          openCell.textContent = "—";
        }
        row.appendChild(openCell);
        const detailsCell = document.createElement("td");
        const detailsLink = document.createElement("a");
        detailsLink.href = "#job-" + job.id;
        detailsLink.className = "job-details-link";
        detailsLink.textContent = "View details";
        detailsLink.addEventListener("click", event => {
          event.preventDefault();
          showJobDetails(job);
        });
        detailsCell.appendChild(detailsLink);
        row.appendChild(detailsCell);
        jobsTableBody.appendChild(row);
      }
    }

    async function loadJobs(search = jobsSearchInput.value, page = currentPage) {
      const searchId = ++activeSearch;
      jobsListStatus.className = "message";
      jobsListStatus.textContent = "Loading jobs…";
      jobsPreviousPage.disabled = true;
      jobsNextPage.disabled = true;
      try {
        const response = await fetch(
          "/api/jobs-list?q=" + encodeURIComponent(search) + "&page=" + page
        );
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not load jobs.");
        if (searchId !== activeSearch) return;
        renderJobs(result.jobs);
        currentPage = result.page;
        jobsPageStatus.textContent = `Page ${result.page} of ${result.total_pages}`;
        jobsPreviousPage.disabled = result.page <= 1;
        jobsNextPage.disabled = result.page >= result.total_pages;
        jobsListStatus.textContent =
          `${result.total_matches.toLocaleString()} matching jobs · ` +
          `showing ${result.jobs.length} on this page · ${result.limit} per page`;
      } catch (error) {
        if (searchId !== activeSearch) return;
        jobsTableBody.replaceChildren();
        const row = document.createElement("tr");
        const cell = addJobCell(
          row,
          error.message || "Could not load jobs.",
          "empty",
        );
        cell.colSpan = 9;
        jobsTableBody.appendChild(row);
        jobsListStatus.className = "message error";
        jobsListStatus.textContent = error.message || "Could not load jobs.";
        jobsPageStatus.textContent = "Page unavailable";
      }
    }

    document.getElementById("jobs-search-form").addEventListener("submit", event => {
      event.preventDefault();
      clearTimeout(searchTimer);
      currentPage = 1;
      loadJobs(jobsSearchInput.value, currentPage);
    });
    jobsSearchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        currentPage = 1;
        loadJobs(jobsSearchInput.value, currentPage);
      }, 250);
    });
    jobsPreviousPage.addEventListener("click", () => {
      if (currentPage > 1) loadJobs(jobsSearchInput.value, currentPage - 1);
    });
    jobsNextPage.addEventListener("click", () => {
      loadJobs(jobsSearchInput.value, currentPage + 1);
    });
    document.getElementById("close-job-details").addEventListener("click", () => {
      jobDetailsDialog.close();
    });
    jobDetailsDialog.addEventListener("click", event => {
      if (event.target === jobDetailsDialog) jobDetailsDialog.close();
    });
    loadJobs("");
  </script>
</body>
</html>
"""

PAGE_HTML = PAGE_HTML.replace("<!-- SHARED_HEADER -->", render_header("jobs-list"))
