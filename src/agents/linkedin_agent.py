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
        print("No LinkedIn jobs found.")
        return

    print(
        f"Retrieved {len(jobs)} LinkedIn jobs."
    )

    analyzer = LinkedInAnalyzer()

    playwright = None
    browser = None

    checked = 0
    closed = 0
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
                # Normally these won't be returned by
                # get_linkedin_jobs(), but this protects
                # against a status changing between the
                # SELECT and this point.
                # -----------------------------------------

                current_status = job["job_status"]

                if current_status in {
                    "CLOSED",
                    "DISCARDED",
                }:

                    print(
                        f"→ Skipped "
                        f"({current_status})"
                    )

                    continue

                # -----------------------------------------
                # Open LinkedIn page
                # -----------------------------------------

                _, _, page = await open_page(
                    url=url,
                    headless=HEADLESS,
                    playwright=playwright,
                    browser=browser,
                )

                # -----------------------------------------
                # Analyze page
                # -----------------------------------------

                result = await analyzer.analyze(
                    page
                )

                new_status = result["job_status"]

                # -----------------------------------------
                # Persist status
                # -----------------------------------------

                update_job_status(
                    job_id,
                    new_status,
                )

                # -----------------------------------------
                # Statistics
                # -----------------------------------------

                if new_status == "CLOSED":

                    closed += 1

                    print(
                        "⚠ Job is CLOSED"
                    )

                elif new_status == "DISCARDED":

                    print(
                        "⚠ Job is DISCARDED"
                    )

                else:

                    print(
                        f"✓ {new_status}"
                    )

                checked += 1

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
    print(f"Jobs checked : {checked}")
    print(f"Jobs closed  : {closed}")
    print(f"Failed       : {failed}")
    print("=============================")