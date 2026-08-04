from config import HEADLESS

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer

from database.jobs import (
    get_meupadrinho_jobs,
    update_validation_status,
)

from database.job_details import (
    insert_job_details,
)

from services.browser_service import open_page
from services.json_service import append_analysis


async def run():

    jobs = get_meupadrinho_jobs(limit=3)

    if not jobs:
        print("No pending MeuPadrinho jobs found.")
        return

    print(f"Retrieved {len(jobs)} jobs from database.")

    analyzer = MeuPadrinhoAnalyzer()

    validated = 0
    failed = 0

    total = len(jobs)

    for index, job_data in enumerate(jobs, start=1):

        url = job_data["link"]

        print(f"\n[{index}/{total}] Processing: {url}")

        playwright = None
        browser = None
        page = None

        try:

            playwright, browser, page = await open_page(
                url,
                headless=HEADLESS,
            )

            details = await analyzer.analyze(page)

            # -----------------------------------------
            # Save into database
            # -----------------------------------------

            insert_job_details(
                job_id=job_data["id"],
                details=details,
            )

            update_validation_status(
                job_data["id"],
                "COMPLETED",
            )

            # -----------------------------------------
            # Optional JSON export
            # -----------------------------------------

            details["source_data"] = {
                "id": job_data["id"],
                "original_title": job_data["title"],
                "original_company": job_data["company"],
                "score": job_data["score"],
                "link": job_data["link"],
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

            if browser:
                await browser.close()

            if playwright:
                await playwright.stop()

    print("\n==============================")
    print("Validation finished")
    print(f"Jobs processed : {total}")
    print(f"Validated      : {validated}")
    print(f"Failed         : {failed}")

    if validated:
        print("Database       : job_details")
        print("JSON Export    : output/job_analysis.json")

    print("==============================")