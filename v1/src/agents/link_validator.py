#agents/link_validator.py
import asyncio
from pathlib import Path
import random

from playwright.async_api import async_playwright

from config import (
    HEADLESS,
    VALIDATION_LIMIT,
    OUTPUT_FOLDER,
    VALIDATE_DELAY_MIN,
    VALIDATE_DELAY_MAX,
)

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

MEUPADRINHO_PROFILE_DIR = Path(
    "storage/meupadrinho_edge_profile"
)


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


async def run(limit: int | None = None):

    if limit is None:
        limit = VALIDATION_LIMIT

    jobs = get_meupadrinho_jobs(limit=limit)

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
    requests_on_current_ip = 0

    playwright = None
    browser = None

    try:

        playwright = await async_playwright().start()

        try:
            browser = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(MEUPADRINHO_PROFILE_DIR),
                channel="msedge",
                headless=False,
                chromium_sandbox=True,
            )
        except Exception as error:
            if "opening in existing browser session" in str(error).casefold():
                print(
                    "Microsoft Edge is already using the MeuPadrinho profile. "
                    "Close all Edge windows using this profile and rerun validate."
                )
                return
            raise

        for index, job_data in enumerate(
            jobs,
            start=1
        ):

            job_completed = False

            print(
                f"\n[{index}/{total}] "
                f"{job_data['company']} | "
                f"{job_data['title']}"
            )

            while not job_completed:

                page = None

                try:

                    requests_on_current_ip += 1

                    _, _, page = await open_page(
                        job_data["link"],
                        headless=HEADLESS,
                        playwright=playwright,
                        browser=browser,
                    )

                    details = await analyzer.analyze(page)

                    # -----------------------------------------
                    # Check for Rate Limit (HTTP 429 / WAF)
                    # -----------------------------------------
                    if details.get("rate_limited"):

                        if page:
                            await page.close()
                            page = None

                        print("\n" + "=" * 65)
                        print(" [!] RATE LIMIT (HTTP 429) DETECTED ON MEUPADRINHO")
                        print(f"     Job: {job_data['company']} | {job_data['title']}")
                        print(f"     Requests made on this VPN/IP session: {requests_on_current_ip}")
                        print("=" * 65)
                        print("MeuPadrinho has blocked requests from your current IP address.")
                        print("\n Steps to resume:")
                        print("   1. Open the Proton VPN app on your computer.")
                        print("   2. Switch to another server or country (e.g. Quick Connect).")
                        print("   3. Verify internet is connected.")
                        print("   4. Press [ENTER] below to retry this job with your new IP.")
                        print("      (or type 'skip' to skip this job, 'quit' to exit)")
                        print("=" * 65)

                        raw_choice = await asyncio.to_thread(
                            input,
                            "\nPress [ENTER] after reconnecting Proton VPN: "
                        )
                        choice = raw_choice.strip().lower()

                        if choice in ("q", "quit", "exit"):
                            print("\nExiting validation loop early as requested.")
                            return

                        if choice in ("s", "skip"):
                            print(f"\nSkipped job #{job_data['id']}; remaining as PENDING.")
                            job_completed = True
                            break

                        print("\n[+] Reconnected! Waiting 3s for network to stabilize before retry...")
                        await asyncio.sleep(3)
                        requests_on_current_ip = 0
                        continue

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
                        (
                            "PAGE_NOT_FOUND"
                            if details.get("page_not_found")
                            else "COMPLETED"
                        ),
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
                    job_completed = True

                    # -----------------------------------------
                    # Console output
                    # -----------------------------------------

                    if details["page_not_found"]:

                        print("[!] Page not found -> CLOSED")

                    elif details["job_status"] == "DISCARDED":

                        discarded += 1

                        print(
                            f"[!] Discarded -> "
                            f"Level: {details.get('level', '')}"
                        )

                    elif details["job_status"] == "CLOSED":

                        print("[!] Job closed")

                    else:

                        print("[OK] Validated -> NEW")

                except Exception as error:

                    error_msg = str(error).casefold()

                    if any(
                        net_err in error_msg
                        for net_err in (
                            "err_network_changed",
                            "err_connection_reset",
                            "err_internet_disconnected",
                            "err_connection_aborted",
                        )
                    ):
                        print(f"\n[!] Network state changed during request: {error}")
                        print("Waiting 3s for network to recover before retrying...")
                        await asyncio.sleep(3)
                        continue

                    failed += 1

                    update_validation_status(
                        job_data["id"],
                        "FAILED",
                    )

                    print(
                        f"[X] Failed: {error}"
                    )
                    job_completed = True

                finally:

                    if page:
                        await page.close()

            # Pacing delay between jobs to prevent rate limiting
            if index < total and job_completed:
                delay = random.uniform(
                    VALIDATE_DELAY_MIN,
                    VALIDATE_DELAY_MAX,
                )
                await asyncio.sleep(delay)

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