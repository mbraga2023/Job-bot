#agents/linkedin_agent.py
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from config import HEADLESS

from services.linkedin_session import LinkedInSession
from agents.analyzers.linkedin import LinkedInAnalyzer
from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer

from database.job_details import (
    get_linkedin_jobs,
    update_application_url,
    update_job_source,
    update_job_status,
)
from database.jobs import update_job_link

MEUPADRINHO_PROFILE_DIR = Path(
    "storage/meupadrinho_edge_profile"
)


async def run():
    jobs = get_linkedin_jobs(limit=100)

    if not jobs:
        print("No pending LinkedIn jobs found.")
        return

    print(f"Retrieved {len(jobs)} pending LinkedIn jobs.")

    analyzer = LinkedInAnalyzer()
    meupadrinho_analyzer = MeuPadrinhoAnalyzer()
    session = LinkedInSession(headless=HEADLESS)
    needs_edge = any(
        "meupadrinho" in str(job["application_url"] or "").casefold()
        for job in jobs
    )
    edge_playwright = None
    edge_context = None
    edge_page = None

    checked = 0
    opened = 0
    closed = 0
    not_remote = 0
    failed = 0

    total = len(jobs)

    try:
        if needs_edge:
            MEUPADRINHO_PROFILE_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )
            edge_playwright = await async_playwright().start()

            try:
                edge_context = await edge_playwright.chromium.launch_persistent_context(
                    user_data_dir=str(MEUPADRINHO_PROFILE_DIR),
                    channel="msedge",
                    headless=False,
                    chromium_sandbox=True,
                )
            except Exception as error:
                if "opening in existing browser session" in str(error).casefold():
                    print(
                        "Microsoft Edge is already using the MeuPadrinho profile. "
                        "Close all Edge windows using this profile and rerun linkedin."
                    )
                    return
                raise

            edge_page = (
                edge_context.pages[0]
                if edge_context.pages
                else await edge_context.new_page()
            )

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

                if "meupadrinho" in str(url or "").casefold():
                    await edge_page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )
                    await meupadrinho_analyzer.wait_for_content(
                        edge_page
                    )
                    resolved_url = await meupadrinho_analyzer.get_apply_button(
                        edge_page
                    )

                    if not resolved_url:
                        failed += 1
                        print(
                            "✗ MeuPadrinho application link not found; "
                            "keeping status NEW for retry."
                        )
                        continue

                    url = urljoin(edge_page.url, resolved_url)

                    if "linkedin.com/jobs" not in url.casefold():
                        failed += 1
                        print(
                            "✗ MeuPadrinho link did not resolve to a LinkedIn job; "
                            "keeping the current URL and status NEW."
                        )
                        continue

                    update_application_url(job_id, url)
                    print(f"Resolved application URL: {url}")

                if "linkedin.com/jobs" not in str(url or "").casefold():
                    failed += 1
                    print(
                        "✗ Application URL did not resolve to a LinkedIn job; "
                        "keeping status NEW for retry."
                    )
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

                if result["easy_apply"]:
                    update_job_source(
                        job_id,
                        "linkedin_Easy_Apply",
                    )

                if update_job_link(job_id, url):
                    print("Updated job link to LinkedIn page.")
                else:
                    print("⚠ LinkedIn page link is already assigned to another job.")

                update_job_status(
                    job_id,
                    new_status,
                )

                checked += 1

                if new_status == "OPEN":
                    opened += 1
                    if result["easy_apply"]:
                        print("✓ Job is OPEN + EASY APPLY")
                    else:
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
        if edge_context:
            await edge_context.close()

        if edge_playwright:
            await edge_playwright.stop()

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
