#agents/linkedin_agent.py
from playwright.async_api import async_playwright

from config import HEADLESS

from services.browser_service import open_page

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

    print(
        f"Retrieved {len(jobs)} pending LinkedIn jobs."
    )

    analyzer = LinkedInAnalyzer()

    playwright = None
    browser = None

    checked = 0
    opened = 0
    closed = 0
    not_remote = 0
    failed = 0

    total = len(jobs)

    try:

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=HEADLESS
        )

        for index, job in enumerate(
            jobs,
            start=1
        ):

            page = None

            job_id = job["job_id"]
            url = job["application_url"]

            print(
                f"\n[{index}/{total}] "
                f"{job['company']} | "
                f"{job['title']}"
            )

            print(f"URL: {url}")

            try:

                # -----------------------------------------
                # Safety check
                # -----------------------------------------

                if job["job_status"] != "NEW":

                    print(
                        f"→ Skipped "
                        f"({job['job_status']})"
                    )

                    continue

                # -----------------------------------------
                # Open LinkedIn
                # -----------------------------------------

                _, _, page = await open_page(
                    url=url,
                    headless=HEADLESS,
                    playwright=playwright,
                    browser=browser,
                )

                # -----------------------------------------
                # Analyze
                # -----------------------------------------

                result = await analyzer.analyze(page)

                new_status = result["job_status"]

                # -----------------------------------------
                # Update database
                # -----------------------------------------

                update_job_status(
                    job_id,
                    new_status,
                )

                checked += 1

                # -----------------------------------------
                # Result
                # -----------------------------------------

                if new_status == "OPEN":

                    opened += 1

                    print(
                        "✓ Job is OPEN"
                    )

                elif new_status == "CLOSED":

                    closed += 1

                    print(
                        "⚠ Job is CLOSED"
                    )

                elif new_status == "NOT_REMOTE":

                    not_remote += 1

                    print(
                        "⚠ Job is NOT REMOTE"
                    )

                else:

                    print(
                        f"⚠ Unexpected status: "
                        f"{new_status}"
                    )

            except Exception as error:

                failed += 1

                print(
                    f"✗ Failed: {error}"
                )

            finally:

                if page:
                    await page.close()

    finally:

        if browser:
            await browser.close()

        if playwright:
            await playwright.stop()

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