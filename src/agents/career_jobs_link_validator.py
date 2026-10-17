#/agents/career_jobs_link_validator.py
from playwright.async_api import async_playwright

from config import HEADLESS

from agents.analyzers.career_jobs_links import (
    CareerJobsLinksAnalyzer,
)

from database.career_job_details import (
    get_generic_job_links,
    insert_career_job_details,
    update_career_job_status,
)

from services.browser_service import open_page
from services.json_service import append_analysis
from services.published_date import normalize_published_date
from services.career_job_review import discard_ineligible_new_career_jobs


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

    if any(keyword in level for keyword in ("junior", "júnior", "estagio", "estágio", "estagiario", "estagiário", "estagiária", "estagiaria", "senior", "sênior")):
        return True

    return False


async def run():

    discarded_existing = discard_ineligible_new_career_jobs()
    if any(discarded_existing.values()):
        print(
            "[INFO] Existing NEW career jobs discarded: "
            f"{discarded_existing['junior']} junior, "
            f"{discarded_existing['stale']} older than 30 days."
        )

    # ---------------------------------------------------------
    # Get career jobs whose URL is NOT already represented
    # in career_job_details.
    # ---------------------------------------------------------

    jobs = get_generic_job_links(
        limit=200
    )

    if not jobs:

        print(
            "No pending career jobs found."
        )

        return

    print(
        f"Retrieved {len(jobs)} jobs from database."
    )

    analyzer = CareerJobsLinksAnalyzer()

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
            start=1,
        ):

            page = None

            print(
                f"\n[{index}/{total}] "
                f"{job_data['company']} | "
                f"{job_data['title']}"
            )

            try:

                # -------------------------------------------------
                # Validate source URL
                # -------------------------------------------------

                _, _, page = await open_page(
                    job_data["url"],
                    headless=HEADLESS,
                    playwright=playwright,
                    browser=browser,
                )

                details = await analyzer.analyze(
                    page
                )
                details["published_date"] = normalize_published_date(
                    details.get("published_date")
                )

                # -------------------------------------------------
                # Determine job status
                # -------------------------------------------------

                if details.get(
                    "page_not_found"
                ):

                    details["job_status"] = (
                        "CLOSED"
                    )

                elif should_discard(
                    details
                ):

                    details["job_status"] = (
                        "DISCARDED"
                    )

                elif details.get(
                    "job_status"
                ) == "CLOSED":

                    details["job_status"] = (
                        "CLOSED"
                    )

                else:

                    details["job_status"] = (
                        "NEW"
                    )

                # -------------------------------------------------
                # Save validated career job details
                # -------------------------------------------------

                insert_career_job_details(
                    career_job_id=job_data["id"],
                    source_url=job_data["url"],
                    details=details,
                )

                # -------------------------------------------------
                # Update career job status
                # -------------------------------------------------

                update_career_job_status(
                    job_data["id"],
                    details["job_status"],
                )

                append_analysis(
                    details
                )

                validated += 1

                # -------------------------------------------------
                # Console output
                # -------------------------------------------------

                if details["page_not_found"]:

                    print(
                        "⚠ Page not found → CLOSED"
                    )

                elif (
                    details["job_status"]
                    == "DISCARDED"
                ):

                    discarded += 1

                    print(
                        "⚠ Discarded → "
                        f"Level: "
                        f"{details.get('level', '')}"
                    )

                elif (
                    details["job_status"]
                    == "CLOSED"
                ):

                    print(
                        "⚠ Job closed"
                    )

                else:

                    print(
                        "✓ Validated → NEW"
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

    print(
        "\n=============================="
    )

    print(
        "Validation Summary"
    )

    print(
        "=============================="
    )

    print(
        f"Jobs processed : {total}"
    )

    print(
        f"Validated      : {validated}"
    )

    print(
        f"Discarded      : {discarded}"
    )

    print(
        f"Failed         : {failed}"
    )

    print(
        "Database       : career_job_details"
    )

    print(
        "=============================="
    )


if __name__ == "__main__":

    import asyncio

    asyncio.run(run())