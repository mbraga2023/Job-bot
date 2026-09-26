#agents/link_validator.py
from playwright.async_api import async_playwright

from config import HEADLESS, OUTPUT_FOLDER

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer

from database.jobs import (
    get_meupadrinho_jobs,
    update_validation_status,
)

from database.job_details import (
    insert_job_details,
    update_job_status,
)

from services.browser_service import open_page
from services.json_service import append_analysis


def should_discard(details: dict) -> bool:
    """
    Keep only mid-level positions.

    Junior, estágio, and senior roles are discarded.
    """

    level = (
        details.get("level", "")
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )

    level = " ".join(level.split())

    if not level:
        return False

    discarded_levels = {
        "junior",
        "júnior",
        "junior level",
        "estagio",
        "estágio",
        "estagiario",
        "estagiário",
        "estagiária",
        "estagiaria",
        "intern",
        "trainee",
        "senior",
        "sênior",
        "sr",
    }

    if level in discarded_levels:
        return True

    if any(keyword in level for keyword in ("junior", "júnior", "estagio", "estágio", "estagiario", "estagiário", "estagiária", "estagiaria", "senior", "sênior")):
        return True

    return False


async def run():

    jobs = get_meupadrinho_jobs(limit=20)

    if not jobs:
        print("No pending MeuPadrinho jobs found.")
        return

    print(
        f"Retrieved {len(jobs)} jobs from database."
    )

    analyzer = MeuPadrinhoAnalyzer()

    validated = 0
    failed = 0
    discarded = 0

    total = len(jobs)

    playwright = None
    browser = None

    try:

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=HEADLESS
        )

        for index, job_data in enumerate(
            jobs,
            start=1
        ):

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

                # -----------------------------------------
                # Determine job status
                # -----------------------------------------

                if details.get("page_not_found"):

                    details["job_status"] = "CLOSED"

                elif should_discard(details):

                    details["job_status"] = "DISCARDED"

                elif details.get("job_status") == "CLOSED":

                    details["job_status"] = "CLOSED"

                else:

                    details["job_status"] = "NEW"

                # -----------------------------------------
                # Save job details
                # -----------------------------------------

                insert_job_details(
                    job_id=job_data["id"],
                    details=details,
                )

                # -----------------------------------------
                # Update job status
                # -----------------------------------------

                update_job_status(
                    job_data["id"],
                    details["job_status"],
                )

                # -----------------------------------------
                # Validation completed
                # -----------------------------------------

                update_validation_status(
                    job_data["id"],
                    "COMPLETED",
                )

                # -----------------------------------------
                # Optional JSON export
                # -----------------------------------------

                details["source_data"] = {
                    "job_id": job_data["id"],
                    "telegram_title": job_data["title"],
                    "telegram_company": job_data["company"],
                    "telegram_link": job_data["link"],
                    "created_at": job_data["created_at"],
                }

                append_analysis(details)

                validated += 1

                # -----------------------------------------
                # Console output
                # -----------------------------------------

                if details["page_not_found"]:

                    print("⚠ Page not found → CLOSED")

                elif details["job_status"] == "DISCARDED":

                    discarded += 1

                    print(
                        f"⚠ Discarded → "
                        f"Level: {details.get('level', '')}"
                    )

                elif details["job_status"] == "CLOSED":

                    print("⚠ Job closed")

                else:

                    print("✓ Validated → NEW")

            except Exception as error:

                failed += 1

                update_validation_status(
                    job_data["id"],
                    "FAILED",
                )

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

    print("\n==============================")
    print("Validation Summary")
    print("==============================")
    print(f"Jobs processed : {total}")
    print(f"Validated      : {validated}")
    print(f"Discarded      : {discarded}")
    print(f"Failed         : {failed}")

    if validated:
        print("Database       : job_details")
        print(
            f"JSON Export    : "
            f"{OUTPUT_FOLDER / 'job_analysis.json'}"
        )

    print("==============================")