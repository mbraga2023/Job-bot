#link_validator.py
from config import HEADLESS

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer

from database.jobs import (
    get_meupadrinho_jobs,
    update_validation_status,
)

from database.job_details import insert_job_details

from services.browser_service import open_page
from services.json_service import append_analysis


async def run():

    jobs = get_meupadrinho_jobs()

    if not jobs:
        print("No MeuPadrinho jobs found.")
        return

    print(f"Retrieved {len(jobs)} jobs from database.")

    analyzer = MeuPadrinhoAnalyzer()

    results = []

    total = len(jobs)

    for index, job_data in enumerate(jobs, start=1):

        url = job_data["link"]

        print(f"\n[{index}/{total}] Processing: {url}")

        playwright, browser, page = await open_page(
            url,
            headless=HEADLESS,
        )

        try:

            details = await analyzer.analyze(page)

            # -------------------------------------------------
            # Save into database
            # -------------------------------------------------

            insert_job_details(
                job_id=job_data["id"],
                details=details,
            )

            update_validation_status(
                job_data["id"],
                "COMPLETED",
            )

            # -------------------------------------------------
            # Optional JSON export (debug/history)
            # -------------------------------------------------

            details["source_data"] = {

                "id": job_data["id"],
                "original_title": job_data["title"],
                "original_company": job_data["company"],
                "score": job_data["score"],
                "link": job_data["link"],
                "created_at": job_data["created_at"],

            }

            append_analysis(details)

            results.append(details)

            if details["page_not_found"]:
                print("⚠ Page not found")
            else:
                print("✓ Validated")

        except Exception as error:

            update_validation_status(
                job_data["id"],
                "FAILED",
            )

            print(f"✗ Failed: {error}")

        finally:

            await browser.close()
            await playwright.stop()

    print("\n==============================")
    print("Validation finished")
    print(f"Jobs retrieved : {total}")
    print(f"Jobs validated : {len(results)}")

    if results:
        print("Database       : job_details")
        print("JSON Export    : output/job_analysis.json")

    print("==============================")