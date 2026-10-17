import html

from database.career_job_details import (
    get_new_career_job_details,
    update_career_job_status,
)
from services.browser_launcher import open_in_chrome
from services.career_job_review import discard_ineligible_new_career_jobs


def run():
    """Open eligible NEW career job pages in Chrome for manual review."""
    discarded = discard_ineligible_new_career_jobs()
    jobs = get_new_career_job_details()

    print(
        "[INFO] Discarded "
        f"{discarded['junior']} junior and {discarded['stale']} stale career jobs."
    )

    if not jobs:
        print("[INFO] No eligible NEW career jobs to open.")
        return

    urls = []
    career_job_ids = []
    for index, job in enumerate(jobs, start=1):
        url = job.get("source_url")
        if not url:
            continue

        title = html.unescape(job.get("title") or "Untitled").strip()
        company = html.unescape(job.get("company") or "Unknown").strip()
        print(f"[{index}/{len(jobs)}] {company} - {title}")
        print(f"    -> {url}")
        urls.append(url)
        career_job_ids.append(job["career_job_id"])

    if not urls:
        print("[INFO] No eligible career jobs have a source URL.")
        return

    success, message = open_in_chrome(urls)
    if not success:
        print(f"[ERROR] {message}")
        return

    for career_job_id in career_job_ids:
        update_career_job_status(career_job_id, "MANUAL")

    print(f"[OK] {message}")
    print(f"[OK] Marked {len(career_job_ids)} career jobs as MANUAL.")
