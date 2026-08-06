from playwright.async_api import async_playwright

from config import HEADLESS, OUTPUT_FOLDER

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer

from database.jobs import (
    get_meupadrinho_jobs,
    update_validation_status,
)

from database.job_details import insert_job_details

from services.browser_service import open_page
from services.json_service import append_analysis


async def run():

    jobs = get_meupadrinho_jobs(limit=50)

    if not jobs:
        print("No pending MeuPadrinho jobs found.")
        return

    print(f"Retrieved {len(jobs)} jobs from database.")

    analyzer = MeuPadrinhoAnalyzer()

    validated = 0
    failed = 0
    total = len(jobs)

    playwright = None
    browser = None

    try:

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=HEADLESS
        )

        for index, job_data in enumerate(jobs, start=1):

            page = None

            print(
                f"\n[{index}/{total}] "
                f"{job_data['company']} | "
                f"{job_data['title']}"
            )

            try:

                _, _, page = await open_page(
                    job_data["link"],
                    headless=HEADLESS,
                    playwright=playwright,
                    browser=browser,
                )

                details = await analyzer.analyze(page)

                insert_job_details(
                    job_id=job_data["id"],
                    details=details,
                )

                update_validation_status(
                    job_data["id"],
                    "COMPLETED",
                )

                # Optional JSON export
                details["source_data"] = {
                    "job_id": job_data["id"],
                    "telegram_title": job_data["title"],
                    "telegram_company": job_data["company"],
                    "telegram_link": job_data["link"],
                    "created_at": job_data["created_at"],
                }

                append_analysis(details)

                validated += 1

                if details["page_not_found"]:
                    print("⚠ Page not found")
                else:
                    print("✓ Validated")

            except Exception as error:

                failed += 1

                update_validation_status(
                    job_data["id"],
                    "FAILED",
                )

                print(f"✗ Failed: {error}")

            finally:

                if page:
                    await page.close()

    finally:

        if browser:
            await browser.close()

        if playwright:
            await playwright.stop()

    print("\n==============================")
    print("Validation Summary")
    print("==============================")
    print(f"Jobs processed : {total}")
    print(f"Validated      : {validated}")
    print(f"Failed         : {failed}")

    if validated:
        print("Database       : job_details")
        print(f"JSON Export    : {OUTPUT_FOLDER / 'job_analysis.json'}")

    print("==============================")