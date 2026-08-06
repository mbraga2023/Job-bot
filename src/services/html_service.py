from html import escape
from pathlib import Path

from database.dashboard import get_dashboard_jobs


OUTPUT = Path("output/dashboard.html")

STATUS_OPTIONS = [
    "NEW",
    "INTERESTED",
    "APPLIED",
    "INTERVIEW",
    "REJECTED",
    "ACCEPTED",
    "DISCARDED",
]


def text(value, default="-"):
    if value is None or str(value).strip() == "":
        return default
    return escape(str(value))


def link(url, label):
    if not url:
        return "-"
    safe_url = escape(str(url), quote=True)
    return f'<a href="{safe_url}" target="_blank" rel="noopener">{label}</a>'


def generate_dashboard():
    jobs = get_dashboard_jobs()
    rows = []

    for job in jobs:
        title = job["title"]
        company = job["company"]
        location = job["location"]
        level = job["level"]
        remote_value = job["remote"]
        status = job["job_status"] or "NEW"

        page_status = "REMOVED" if job["page_not_found"] else "FOUND"
        application_url = job["application_url"] or job["link"]

        options = "".join(
            f'<option value="{escape(option)}" '
            f'{"selected" if status == option else ""}>{escape(option)}</option>'
            for option in STATUS_OPTIONS
        )

        rows.append(f"""
        <tr>
            <td>{text(job["published_date"])}</td>
            <td>{text(job["category"])}</td>
            <td>{text(title)}</td>
            <td>{text(company)}</td>
            <td>{text(location)}</td>
            <td>{text(level)}</td>
            <td>{"YES" if remote_value else "NO"}</td>
            <td>{page_status}</td>
            <td>{text(job["contract"])}</td>
            <td>{text(job["job_source"])}</td>
            <td>{text(job["application_source"])}</td>
            <td>{text(job["ai_status"])}</td>
            <td>
                <select onchange="updateStatus({job['id']}, this.value)">
                    {options}
                </select>
            </td>
            <td>
                <button>{link(job["link"], "Details")} 
                </button>
                <button>
                    {link(application_url, "Apply")}
                </button>
            </td>
            <td>
                <details>
                    <summary>View</summary>
                    <strong>Description</strong>
                    <p>{text(job["description"])}</p>
                    <strong>Technologies</strong>
                    <p>{text(job["technologies"])}</p>
                    <strong>Requirements</strong>
                    <p>{text(job["requirements"])}</p>
                    <strong>Differentials</strong>
                    <p>{text(job["differentials"])}</p>
                    <strong>Benefits</strong>
                    <p>{text(job["benefits"])}</p>
                    <small>Validated: {text(job["validated_at"])}</small>
                </details>
            </td>
        </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Job Dashboard</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 30px; color: #222; }}
h1 {{ margin-bottom: 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{ background: #222; color: white; padding: 10px; text-align: left; position: sticky; top: 0; }}
td {{ padding: 8px; border-bottom: 1px solid #ddd; vertical-align: top; }}
tr:hover {{ background: #f4f4f4; }}
.score {{ font-weight: bold; text-align: center; }}
select {{ padding: 5px; }}
a {{ text-decoration: none; }}
details {{ max-width: 420px; line-height: 1.4; }}
details p {{ white-space: pre-wrap; max-height: 180px; overflow: auto; }}
.table-wrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<h1>AI Job Search Dashboard</h1>
<p>Total jobs: {len(jobs)}</p>
<div class="table-wrap">
<table>
<thead><tr>
<th>Published</th><th>Category</th><th>Title</th>
<th>Company</th><th>Location</th><th>Level</th><th>Remote</th>
<th>Page</th><th>Contract</th><th>Source</th><th>Application Source</th>
<th>AI Status</th><th>Job Status</th><th>Links</th><th>Validated Data</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</div>
<script>
function updateStatus(jobId, status) {{
    console.log("Update job:", jobId, status);
}}
</script>
</body>
</html>"""

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    return OUTPUT
