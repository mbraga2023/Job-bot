"""LinkedIn Session & Status Validator for v2."""

from __future__ import annotations

import asyncio
from playwright.async_api import async_playwright

from v2.config import config
from v2.core.database import get_connection, update_job_status, update_job_validation
from v2.flows.telegram.analyzers.linkedin import LinkedInAnalyzer, is_linkedin_person_url


async def run_linkedin_validator(limit: int = 100) -> None:
    """Validate active status of pending LinkedIn jobs."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM jobs
            WHERE pipeline = 'TELEGRAM'
              AND status = 'VALIDATED'
              AND (
                  application_url LIKE '%linkedin.com%'
                  OR source_url LIKE '%linkedin.com%'
              )
            ORDER BY id ASC
            LIMIT ?
        """, (limit,))
        jobs = [dict(r) for r in cursor.fetchall()]

    if not jobs:
        print("\n[INFO] No pending LinkedIn jobs found to verify.\n")
        return

    print("\n" + "=" * 60)
    print(f"[LINKEDIN] Verifying {len(jobs)} LinkedIn job postings...")
    print("=" * 60)

    profile_dir = config.linkedin_profile_dir
    profile_dir.mkdir(parents=True, exist_ok=True)
    analyzer = LinkedInAnalyzer()

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=config.headless,
            viewport={"width": 1440, "height": 900},
        )
        page = context.pages[0] if context.pages else await context.new_page()

        opened_count = 0
        easy_apply_count = 0
        closed_count = 0
        recruiter_count = 0

        try:
            for index, job in enumerate(jobs, start=1):
                target_url = job.get("application_url") or job.get("source_url")
                print(f"\n[{index}/{len(jobs)}] Checking LinkedIn: {target_url}")

                person_url = next(
                    (
                        url
                        for url in (job.get("application_url"), job.get("source_url"))
                        if is_linkedin_person_url(url)
                    ),
                    None,
                )
                if person_url:
                    update_job_status(job["id"], "RECRUITER")
                    recruiter_count += 1
                    print(
                        f" [RECRUITER] ID {job['id']} is a LinkedIn person page; "
                        "status set to RECRUITER."
                    )
                    continue

                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
                except Exception as exc:
                    print(f" [!] Navigation failed: {exc}")
                    continue

                if is_linkedin_person_url(page.url):
                    update_job_status(job["id"], "RECRUITER")
                    recruiter_count += 1
                    print(
                        f" [RECRUITER] ID {job['id']} redirected to a LinkedIn person page; "
                        "status set to RECRUITER."
                    )
                    continue

                analysis = await analyzer.analyze(page)
                status = analysis.get("job_status", "OPEN")
                if status == "CLOSED":
                    closed_count += 1
                    update_job_status(job["id"], "CLOSED", discard_reason="LINKEDIN_CLOSED")
                    print(f" [CLOSED] {job.get('company')} - {job.get('title')}")
                elif analysis.get("easy_apply"):
                    easy_apply_count += 1
                    update_job_validation(
                        job_id=job["id"],
                        status="EASY_APPLY",
                        remote=1 if analysis.get("remote") else (0 if analysis.get("remote") is False else None),
                    )
                    print(f" [EASY APPLY] {job.get('company')} - {job.get('title')}")
                else:
                    app_url = await analyzer.get_application_url(page)
                    opened_count += 1
                    update_job_validation(
                        job_id=job["id"],
                        status="OPEN",
                        application_url=app_url if app_url else None,
                        remote=1 if analysis.get("remote") else (0 if analysis.get("remote") is False else None),
                    )
                    if app_url:
                        print(
                            f" [OPEN] {job.get('company')} - {job.get('title')} "
                            f"(Apply URL: {app_url})"
                        )
                    else:
                        print(
                            f" [OPEN] {job.get('company')} - {job.get('title')} "
                            "(Apply URL not found; existing URL left unchanged)"
                        )

                await asyncio.sleep(2.0)

        finally:
            await context.close()

    print("\n" + "=" * 60)
    print("[SUMMARY] LINKEDIN VERIFICATION METRICS")
    print("=" * 60)
    print(f" Confirmed OPEN   : {opened_count}")
    print(f" Easy Apply       : {easy_apply_count}")
    print(f" Confirmed CLOSED : {closed_count}")
    print(f" Recruiter pages  : {recruiter_count}")
    print("=" * 60 + "\n")


def run(limit: int = 100) -> None:
    """Synchronous entry point."""
    asyncio.run(run_linkedin_validator(limit=limit))
