"""Companies page view."""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot v2.0 Companies</title>
  <style>
    :root { color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { margin: 0; background: #0b0f19; color: #e2e8f0; }
    header { background: #131b2e; border-bottom: 1px solid #1e293b; padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; gap: 24px; }
    header h1 { margin: 0; font-size: 20px; font-weight: 700; color: #60a5fa; }
    .tabs { display: flex; gap: 8px; }
    .tabs a { padding: 9px 14px; border-radius: 8px; color: #94a3b8; text-decoration: none; font-size: 14px; font-weight: 600; }
    .tabs a:hover, .tabs a.active { background: #1e293b; color: #f8fafc; }
    main { max-width: 1200px; margin: 32px auto; padding: 0 24px; }
    .panel { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
    h2 { margin: 0 0 18px; font-size: 18px; }
    form { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; align-items: end; }
    label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 6px; }
    input { width: 100%; box-sizing: border-box; background: #0b0f19; border: 1px solid #334155; border-radius: 6px; padding: 10px; color: #f8fafc; font-size: 14px; }
    button { border: 0; border-radius: 8px; padding: 10px 18px; background: #2563eb; color: white; font-size: 14px; font-weight: 500; cursor: pointer; }
    button:hover:not(:disabled) { background: #3b82f6; }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th, td { padding: 12px 14px; border-bottom: 1px solid #1e293b; }
    th { color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
    td a { color: #93c5fd; }
    .status { color: #86efac; }
    .status.inactive { color: #fca5a5; }
    .empty { color: #94a3b8; text-align: center; padding: 28px; }
    .message { min-height: 20px; margin: 14px 0 0; color: #94a3b8; }
    .message.success { color: #86efac; }
    .message.error { color: #fca5a5; }
    @media (max-width: 760px) {
      header { flex-wrap: wrap; padding: 16px 20px; }
      main { padding: 0 16px; }
      .panel { padding: 18px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Job-bot <span style="color:#94a3b8; font-weight:400;">Version 2.0</span></h1>
    <nav class="tabs" aria-label="Main navigation">
      <a href="/">Dashboard</a>
      <a class="active" href="/companies">Companies</a>
    </nav>
  </header>
  <main>
    <section class="panel">
      <h2>Add Company Career Page</h2>
      <form id="add-company-form">
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
