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
from services.career_job_title_classifier import classify_career_job_title


def get_validation_status(details: dict) -> str:
    if details.get("page_not_found"):
        return "PAGE_NOT_FOUND"

    if details.get("job_status") == "DISCARDED":
        return "JOB_DISCARDED"

    if details.get("job_status") == "CLOSED":
        return "JOB_CLOSED"

    if details.get("job_status") == "EXTRACTION_FAILED":
        return "EXTRACTION_FAILED"

    if details.get("title") or details.get("description"):
        return "JOBS_FOUND"

    return "NO_JOBS_FOUND"


def get_job_status(details: dict) -> str:
    if details.get("page_not_found"):
        return "CLOSED"

    if should_discard(details):
        return "DISCARDED"

    if details.get("job_status") == "CLOSED":
        return "CLOSED"

    if not (details.get("title") or details.get("description")):
        return "EXTRACTION_FAILED"

    return "NEW"


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


def get_discard_reason(details: dict) -> str:
    level = details.get("level") or ""
    return f"detected non-mid-level seniority: {level}" if level else (
        "the extracted seniority is not mid-level"
    )


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

    jobs = get_generic_job_links(limit=None)

    if not jobs:

        print(
            "[STATUS: NO_PENDING_JOBS] No pending career jobs found."
        )

        return

    print(
        f"Retrieved {len(jobs)} jobs from database."
    )

    analyzer = CareerJobsLinksAnalyzer()

    processed = 0
    successfully_extracted = 0
    extraction_failures = 0
    discarded = 0
    exceptions = 0

    total = len(jobs)

    playwright = None
    browser = None

    try:
        for index, job_data in enumerate(
            jobs,
            start=1,
        ):

            page = None
            processed += 1

            print(
                f"\n[{index}/{total}] "
                f"{job_data['company']} | "
                f"{job_data['title']}"
            )

            try:
                decision = await classify_career_job_title(
                    job_data["title"] or ""
                )

                if not decision["is_qa_mid_level"]:
                    details = {
                        "title": job_data["title"],
                        "company": job_data["company"],
                        "location": job_data["location"],
                        "job_status": "DISCARDED",
                        "ai_status": "COMPLETED",
                    }
                    insert_career_job_details(
                        career_job_id=job_data["id"],
                        source_url=job_data["url"],
                        details=details,
                    )
                    append_analysis(
                        {
                            **details,
                            "career_job_id": job_data["id"],
                            "source_url": job_data["url"],
                            "discard_reason": decision["reason"],
                        }
                    )
                    discarded += 1
                    print(
                        "[STATUS: JOB_DISCARDED] "
                        f"Reason: {decision['reason']}"
                    )
                    continue

                if playwright is None:
                    playwright = await async_playwright().start()

                if browser is None:
                    browser = await playwright.chromium.launch(
                        headless=HEADLESS
                    )

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
                    page,
                    fallback={
                        "title": job_data["title"],
                        "company": job_data["company"],
                        "location": job_data["location"],
                    },
                )
                details["ai_status"] = "COMPLETED"
                print(f"  Final URL: {page.url}")
                print(f"  Page title: {await page.title()}")
                print(f"  Extracted keys: {list(details.keys())}")
                print(f"  Extracted title: {details.get('title')!r}")
                print(
                    "  Description length: "
                    f"{len(details.get('description') or '')}"
                )
                print(f"  Page not found: {details.get('page_not_found')}")
                details["published_date"] = normalize_published_date(
                    details.get("published_date")
                )

                # -------------------------------------------------
                # Determine job status
                # -------------------------------------------------

                details["job_status"] = get_job_status(details)
                if details["job_status"] == "DISCARDED":
                    details["discard_reason"] = get_discard_reason(details)
                if details.get("title") or details.get("description"):
                    successfully_extracted += 1
                elif details["job_status"] == "EXTRACTION_FAILED":
                    extraction_failures += 1

                if details["job_status"] == "DISCARDED":
                    discarded += 1

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

                # -------------------------------------------------
                # Console output
                # -------------------------------------------------

                validation_status = get_validation_status(details)

                if validation_status == "PAGE_NOT_FOUND":

                    print(
                        f"[STATUS: {validation_status}] "
                        "⚠ Page not found → CLOSED"
                    )

                elif (
                    validation_status == "JOB_DISCARDED"
                ):

                    print(
                        f"[STATUS: {validation_status}] "
                        "⚠ Discarded → "
                        f"Reason: {details['discard_reason']}"
                    )

                elif (
                    validation_status == "JOB_CLOSED"
                ):

                    print(
                        f"[STATUS: {validation_status}] ⚠ Job closed"
                    )

                elif validation_status == "NO_JOBS_FOUND":

                    print(
                        f"[STATUS: {validation_status}] "
                        "⚠ No job title or description extracted"
                    )

                elif validation_status == "EXTRACTION_FAILED":

                    print(
                        f"[STATUS: {validation_status}] "
                        "⚠ Could not extract job details"
                    )

                else:

                    print(
                        f"[STATUS: {validation_status}] "
                        "✓ Validated → NEW"
                    )

            except Exception as error:

                exceptions += 1

                print(
                    f"[STATUS: VALIDATION_FAILED] ✗ Failed: {error}"
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
        f"Processed                : {processed}"
    )

    print(
        f"Successfully extracted   : {successfully_extracted}"
    )

    print(
        f"Extraction failures      : {extraction_failures}"
    )

    print(
        f"Discarded                 : {discarded}"
    )

    print(
        f"Exceptions                : {exceptions}"
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