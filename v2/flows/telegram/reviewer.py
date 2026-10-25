"""Telegram Flow Reviewer: Opens eligible jobs in Chrome and marks MANUAL."""

from __future__ import annotations

import html
from typing import Sequence

from v2.core.browser import open_urls_in_chrome
from v2.core.database import get_jobs_for_review, update_job_status

MAX_JOBS_PER_BATCH = 10


def run(statuses: Sequence[str] = ("OPEN", "VALIDATED"), limit: int | None = None) -> None:
    """Retrieve eligible Telegram jobs, open them in Chrome, and mark status MANUAL."""
    batch_limit = min(limit, MAX_JOBS_PER_BATCH) if limit and limit > 0 else MAX_JOBS_PER_BATCH
    jobs = get_jobs_for_review(
        pipeline="TELEGRAM",
        statuses=statuses,
        limit=batch_limit,
        remote_only=False,
    )[:batch_limit]

    if not jobs:
        print("\n" + "=" * 60)
        print(" [!] No matching Telegram jobs found to review.")
        print(f"     Target statuses: {', '.join(statuses)}")
        print("=" * 60 + "\n")
        return

    print("\n" + "=" * 65)
    print(f" [CHROME] OPENING TELEGRAM JOBS IN BROWSER ({len(jobs)} jobs)")
    print(f" Target Statuses: {', '.join(statuses)}")
    print("=" * 65)

    urls: list[str] = []
    job_ids: list[int] = []

    for index, job in enumerate(jobs, start=1):
        target_url = job.get("application_url") or job.get("source_url")
        if not target_url:
            continue

        raw_title = job.get("title") or "Untitled"
        title = html.unescape(raw_title).strip()
        company = html.unescape(job.get("company") or "Unknown").strip()
        status = job.get("status") or "NEW"

        print(f" [{index:02d}/{len(jobs):02d}] [{status:<4}] {company} - {title}")
        print(f"        -> {target_url}")

        urls.append(target_url)
        job_ids.append(job["id"])

    print("=" * 65)

    if not urls:
        print("[!] No valid URLs found to open.\n")
        return

    success, message = open_urls_in_chrome(urls)
    if success:
        for jid in job_ids:
            update_job_status(jid, "MANUAL")
        print(f"\n[OK] {message}")
        print(f"[OK] Marked {len(job_ids)} jobs as MANUAL.\n")
    else:
        print(f"\n[X] {message}\n")


if __name__ == "__main__":
    run()
