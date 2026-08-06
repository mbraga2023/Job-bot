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

    print(f"Retrieved {len(jobs)} LinkedIn jobs.")

    analyzer = LinkedInAnalyzer()

    playwright = None
    browser = None

    checked = 0
    failed = 0

    total = len(jobs)

    try:

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=HEADLESS
        )

        for index, job in enumerate(jobs, start=1):

            page = None

            url = job["application_url"]

            print(f"\n[{index}/{total}] {url}")

            try:

                _, _, page = await open_page(
                    url=url,
                    headless=HEADLESS,
                    playwright=playwright,
                    browser=browser,
                )

                result = await analyzer.analyze(page)

                update_job_status(
                    job["job_id"],
                    result["job_status"],

                )

                print(f"✓ {result['job_status']}")
                checked += 1

            except Exception as error:

                failed += 1

                print(f"✗ {error}")

            finally:

                if page:
                    await page.close()

    finally:

        if browser:
            await browser.close()

        if playwright:
            await playwright.stop()

    print("\n=============================")
    print("LinkedIn validation finished")
    print(f"Jobs checked : {checked}")
    print(f"Failed       : {failed}")
    print("=============================")