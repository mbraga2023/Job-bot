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
        <label class="checkbox-field" for="is-international">
          <input id="is-international" name="is_international" type="checkbox">
          International company
        </label>
        <button id="submit-company" type="submit">Add Company</button>
      </form>
      <p id="form-message" class="message" role="status" aria-live="polite"></p>
    </section>
    <section class="panel">
      <h2>Companies</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Company</th><th>Careers URL</th><th>Search URL</th><th>International</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody id="companies-list"><tr><td class="empty" colspan="6">Loading companies...</td></tr></tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const list = document.getElementById("companies-list");
    const message = document.getElementById("form-message");

    function showMessage(text, type = "") {
      message.textContent = text;
      message.className = "message" + (type ? " " + type : "");
    }

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
            link.textContent = value.length > 30 ? value.slice(0, 27) + "..." : value;
            link.title = value;
            cell.appendChild(link);
          } else {
            cell.textContent = value.length > 30 ? value.slice(0, 27) + "..." : value;
            cell.title = value;
          }
        } catch {
          cell.textContent = value.length > 30 ? value.slice(0, 27) + "..." : value;
          cell.title = value;
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
      loadingCell.colSpan = 6;
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
          cell.colSpan = 6;
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
          const international = document.createElement("td");
          international.textContent = company.is_international ? "Yes" : "No";
          row.appendChild(international);
          const status = document.createElement("td");
          status.className = "status" + (company.active ? "" : " inactive");
          status.textContent = company.active ? "Active" : "Inactive";
          row.appendChild(status);

          const actions = document.createElement("td");
          actions.className = "company-actions";
          const editButton = document.createElement("button");
          editButton.type = "button";
          editButton.className = "secondary button-small";
          editButton.textContent = "Edit";
          editButton.addEventListener("click", () => editCompany(company, row));
          actions.appendChild(editButton);

          const activeButton = document.createElement("button");
          activeButton.type = "button";
          activeButton.className = company.active
            ? "warning button-small"
            : "secondary button-small";
          activeButton.textContent = company.active ? "Deactivate" : "Reactivate";
          activeButton.addEventListener("click", () => setCompanyActive(company));
          actions.appendChild(activeButton);
          row.appendChild(actions);
          list.appendChild(row);
        }
      } catch (error) {
        list.replaceChildren();
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.className = "empty";
        cell.colSpan = 6;
        cell.textContent = error.message || "Could not load companies.";
        row.appendChild(cell);
        list.appendChild(row);
      }
    }

    function editCompany(company, row) {
      row.replaceChildren();
      const fields = [
        ["company", company.company, "text"],
        ["careers_url", company.careers_url, "url"],
        ["search_url", company.search_url || "", "url"],
        ["is_international", Boolean(company.is_international), "checkbox"]
      ];
      for (const [name, value, type] of fields) {
        const cell = document.createElement("td");
        const input = document.createElement("input");
        input.type = type;
        input.dataset.field = name;
        if (type === "checkbox") {
          input.checked = value;
          input.setAttribute("aria-label", "International company");
        } else {
          input.value = value;
          input.required = name !== "search_url";
        }
        cell.appendChild(input);
        row.appendChild(cell);
      }

      const status = document.createElement("td");
      status.textContent = company.active ? "Active" : "Inactive";
      row.appendChild(status);

      const actions = document.createElement("td");
      actions.className = "company-actions";
      const saveButton = document.createElement("button");
      saveButton.type = "button";
      saveButton.className = "button-small";
      saveButton.textContent = "Save";
      saveButton.addEventListener("click", () => saveCompany(company.id, row, saveButton));
      actions.appendChild(saveButton);

      const cancelButton = document.createElement("button");
      cancelButton.type = "button";
      cancelButton.className = "secondary button-small";
      cancelButton.textContent = "Cancel";
      cancelButton.addEventListener("click", loadCompanies);
      actions.appendChild(cancelButton);
      row.appendChild(actions);
    }

    async function saveCompany(companyId, row, button) {
      const inputs = Array.from(row.querySelectorAll("input[data-field]"));
      if (inputs.some(input => !input.reportValidity())) return;
      const payload = Object.fromEntries(inputs.map(input => [
        input.dataset.field,
        input.type === "checkbox" ? input.checked : input.value
      ]));
      button.disabled = true;
      try {
        const response = await fetch("/api/companies/" + companyId, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not update company.");
        await loadCompanies();
        showMessage("Company updated successfully.", "success");
      } catch (error) {
        showMessage(error.message || "Could not update company.", "error");
        button.disabled = false;
      }
    }

    async function setCompanyActive(company) {
      const active = !company.active;
      try {
        const response = await fetch("/api/companies/" + company.id, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not update company status.");
        await loadCompanies();
        showMessage(
          active ? "Company reactivated successfully." : "Company deactivated successfully.",
          "success"
        );
      } catch (error) {
        showMessage(error.message || "Could not update company status.", "error");
      }
    }

    document.getElementById("add-company-form").addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.target;
      const button = document.getElementById("submit-company");
      button.disabled = true;
      showMessage("");
      try {
        const response = await fetch("/api/import-career", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            company: form.company.value,
            careers_url: form.careers_url.value,
            search_url: form.search_url.value,
            is_international: form.is_international.checked
          })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not add company.");
        if (result.duplicate) {
          showMessage("This careers website is already registered.");
          return;
        }
        form.reset();
        showMessage("Company added successfully.", "success");
        await loadCompanies();
      } catch (error) {
        showMessage(error.message || "Could not add company.", "error");
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
