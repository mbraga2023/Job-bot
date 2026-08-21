#agents/linkedin_agent.py
from config import HEADLESS

from services.linkedin_session import LinkedInSession
from agents.analyzers.linkedin import LinkedInAnalyzer

from database.job_details import (
    get_linkedin_jobs,
    update_job_status,
)


async def run():
    jobs = get_linkedin_jobs(limit=100)

    if not jobs:
        print("No pending LinkedIn jobs found.")
        return

    print(f"Retrieved {len(jobs)} pending LinkedIn jobs.")

    analyzer = LinkedInAnalyzer()
    session = LinkedInSession(headless=HEADLESS)

    checked = 0
    opened = 0
    closed = 0
    not_remote = 0
    failed = 0

    total = len(jobs)

    try:
        # Starts the persistent browser profile and performs
        # manual login if no active session exists.
        page = await session.get_page()

        print(f"Authenticated browser URL: {page.url}")

        for index, job in enumerate(jobs, start=1):
            job_id = job["job_id"]
            url = job["application_url"]

            print(
                f"\n[{index}/{total}] "
                f"{job['company']} | "
                f"{job['title']}"
            )
            print(f"URL: {url}")

            try:
                if job["job_status"] != "NEW":
                    print(f"→ Skipped ({job['job_status']})")
                    continue

                # Reuse the authenticated page.
                # Do not use open_page() here if it launches another browser.
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )

                await page.wait_for_timeout(2_000)

                result = await analyzer.analyze(page)

                new_status = result["job_status"]

                update_job_status(
                    job_id,
                    new_status,
                )

                checked += 1

                if new_status == "OPEN":
                    opened += 1
                    print("✓ Job is OPEN")

                elif new_status == "CLOSED":
                    closed += 1
                    print("⚠ Job is CLOSED")

                elif new_status == "NOT_REMOTE":
                    not_remote += 1
                    print("⚠ Job is NOT REMOTE")

                else:
                    print(f"⚠ Unexpected status: {new_status}")

            except Exception as error:
                failed += 1
                print(f"✗ Failed: {error}")

    finally:
        # This closes the browser but preserves the profile directory.
        await session.close()

    print()
    print("=============================")
    print("LinkedIn validation finished")
    print("=============================")
    print(f"Jobs retrieved : {total}")
    print(f"Jobs checked   : {checked}")
    print(f"Jobs OPEN      : {opened}")
    print(f"Jobs CLOSED    : {closed}")
    print(f"Not remote     : {not_remote}")
    print(f"Failed         : {failed}")
    print("=============================")
