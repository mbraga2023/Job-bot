"""Companies page view."""

from v2.dashboard.components.header import render_header

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot v2.0 Companies</title>
  <link rel="stylesheet" href="/style/dashboard.css">
</head>
<body class="companies-page">
  <!-- SHARED_HEADER -->
  <main>
    <section class="panel">
      <h2>Add Company Career Page</h2>
      <form id="add-company-form" class="company-form">
        <div>
          <label for="company">Company name</label>
          <input id="company" name="company" required placeholder="e.g. Nubank">
        </div>
        <div>
          <label for="careers-url">Careers URL</label>
          <input id="careers-url" name="careers_url" type="url" required placeholder="https://company.careers.com">
        </div>
        <div>
          <label for="search-url">Search URL (optional)</label>
          <input id="search-url" name="search_url" type="url" placeholder="https://company.careers.com/search?q=qa">
        </div>
        <button id="submit-company" type="submit">Add Company</button>
      </form>
      <p id="form-message" class="message" role="status" aria-live="polite"></p>
    </section>
    <section class="panel">
      <h2>Companies</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Company</th><th>Careers URL</th><th>Search URL</th><th>Status</th></tr></thead>
          <tbody id="companies-list"><tr><td class="empty" colspan="4">Loading companies...</td></tr></tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const list = document.getElementById("companies-list");
    const message = document.getElementById("form-message");

    function addUrlCell(row, value) {
      const cell = document.createElement("td");
      if (value) {
        try {
          const url = new URL(value);
          if (url.protocol === "http:" || url.protocol === "https:") {
            const link = document.createElement("a");
            link.href = url.href;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = value;
            cell.appendChild(link);
          } else {
            cell.textContent = value;
          }
        } catch {
          cell.textContent = value;
        }
      } else {
        cell.textContent = "—";
      }
      row.appendChild(cell);
    }

    async function loadCompanies() {
      list.replaceChildren();
      const loading = document.createElement("tr");
      const loadingCell = document.createElement("td");
      loadingCell.className = "empty";
      loadingCell.colSpan = 4;
      loadingCell.textContent = "Loading companies...";
      loading.appendChild(loadingCell);
      list.appendChild(loading);

      try {
        const response = await fetch("/api/companies");
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not load companies.");
        list.replaceChildren();
        if (result.companies.length === 0) {
          const empty = document.createElement("tr");
          const cell = document.createElement("td");
          cell.className = "empty";
          cell.colSpan = 4;
          cell.textContent = "No companies added yet.";
          empty.appendChild(cell);
          list.appendChild(empty);
          return;
        }

        for (const company of result.companies) {
          const row = document.createElement("tr");
          const name = document.createElement("td");
          name.textContent = company.company;
          row.appendChild(name);
          addUrlCell(row, company.careers_url);
          addUrlCell(row, company.search_url);
          const status = document.createElement("td");
          status.className = "status" + (company.active ? "" : " inactive");
          status.textContent = company.active ? "Active" : "Inactive";
          row.appendChild(status);
          list.appendChild(row);
        }
      } catch (error) {
        list.replaceChildren();
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.className = "empty";
        cell.colSpan = 4;
        cell.textContent = error.message || "Could not load companies.";
        row.appendChild(cell);
        list.appendChild(row);
      }
    }

    document.getElementById("add-company-form").addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.target;
      const button = document.getElementById("submit-company");
      button.disabled = true;
      message.className = "message";
      message.textContent = "";
      try {
        const response = await fetch("/api/import-career", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            company: form.company.value,
            careers_url: form.careers_url.value,
            search_url: form.search_url.value
          })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not add company.");
        if (result.duplicate) {
          message.textContent = "This careers website is already registered.";
          return;
        }
        form.reset();
        message.className = "message success";
        message.textContent = "Company added successfully.";
        await loadCompanies();
      } catch (error) {
        message.className = "message error";
        message.textContent = error.message || "Could not add company.";
      } finally {
        button.disabled = false;
      }
    });

    loadCompanies();
  </script>
</body>
</html>
"""

PAGE_HTML = PAGE_HTML.replace("<!-- SHARED_HEADER -->", render_header("companies"))
