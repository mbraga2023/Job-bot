"""Telegram Jobs Link Validator for v2."""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from v2.config import config
from v2.core.database import get_jobs_for_validation, update_job_validation
from v2.core.date_utils import is_older_than_days, normalize_published_date
from v2.core.seniority import evaluate_seniority
from v2.flows.telegram.analyzers.meupadrinho import MeuPadrinhoAnalyzer


async def run_validator(limit: int | None = None) -> None:
    """Validate discovered Telegram jobs by navigating to their URLs."""
    target_limit = limit or config.validation_limit
    jobs = get_jobs_for_validation(pipeline="TELEGRAM", limit=target_limit)

    if not jobs:
        print("\n[INFO] No pending Telegram jobs found to validate.\n")
        return

    print("\n" + "=" * 60)
    print(f"[VALIDATE] Validating {len(jobs)} pending jobs...")
    print("=" * 60)

    analyzer = MeuPadrinhoAnalyzer()
    profile_dir = config.meupadrinho_profile_dir
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        # Use msedge channel if available or fallback to chromium
        try:
            browser_context = await pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="msedge",
                headless=config.headless,
            )
        except Exception:
            browser_context = await pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=config.headless,
            )

        page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()

        validated_count = 0
        discarded_count = 0
        closed_count = 0

        try:
            for index, job in enumerate(jobs, start=1):
                url = job["source_url"]
                print(f"\n[{index}/{len(jobs)}] Navigating: {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
                except Exception as exc:
                    print(f" [!] Navigation failed: {exc}")
                    continue

                extracted = await analyzer.analyze(page)

                if extracted.get("rate_limited"):
                    print(" [!] Rate limited by remote server. Stopping validation early.")
                    break

                if extracted.get("page_not_found"):
                    print(" [X] Page not found (404 / removed). Marking CLOSED.")
                    update_job_validation(
                        job_id=job["id"],
                        status="CLOSED",
                        discard_reason="PAGE_NOT_FOUND",
                    )
                    closed_count += 1
                    continue

                # Normalizations
                pub_date = normalize_published_date(extracted.get("published_date"))
                final_title = extracted.get("title") or job.get("title")
                final_level = extracted.get("level") or job.get("level")
                final_company = extracted.get("company") or job.get("company")
                final_location = extracted.get("location") or job.get("location")
                final_remote = 1 if extracted.get("remote") else (job.get("remote") or 0)
                app_url = extracted.get("application_url") or url
                app_source = extracted.get("job_source") or "meupadrinho"

                # Check staleness (> 30 days)
                is_stale = is_older_than_days(pub_date, days=30)
                is_seniority_ok, seniority_reason = evaluate_seniority(final_title, final_level)

                status = "VALIDATED"
                discard_reason = None

                if extracted.get("job_status") == "CLOSED":
                    status = "CLOSED"
                    closed_count += 1
                elif is_stale:
                    status = "DISCARDED"
                    discard_reason = "STALE_OVER_30_DAYS"
                    discard_count = discarded_count + 1
                    print(f" [DISCARD] Stale (>30 days): {final_company} - {final_title}")
                elif not is_seniority_ok:
                    status = "DISCARDED"
                    discard_reason = seniority_reason
                    discarded_count += 1
                    print(f" [DISCARD] {seniority_reason}: {final_company} - {final_title} ({final_level})")
                else:
                    status = "VALIDATED"
                    validated_count += 1
                    print(f" [OK] Validated: {final_company} - {final_title}")

                update_job_validation(
                    job_id=job["id"],
                    status=status,
                    title=final_title,
                    company=final_company,
                    location=final_location,
                    remote=final_remote,
                    level=final_level,
                    contract=extracted.get("contract") or job.get("contract"),
                    application_url=app_url,
                    application_source=app_source,
                    description=extracted.get("description"),
                    technologies=extracted.get("technologies"),
                    requirements="\n".join(extracted.get("requirements", [])) if isinstance(extracted.get("requirements"), list) else extracted.get("requirements"),
                    differentials="\n".join(extracted.get("differentials", [])) if isinstance(extracted.get("differentials"), list) else extracted.get("differentials"),
                    benefits="\n".join(extracted.get("benefits", [])) if isinstance(extracted.get("benefits"), list) else extracted.get("benefits"),
                    published_date=pub_date,
                    discard_reason=discard_reason,
                )

                # Delay between requests
                delay = random.uniform(config.validate_delay_min, config.validate_delay_max)
                await asyncio.sleep(delay)

        finally:
            await browser_context.close()

    print("\n" + "=" * 60)
    print("[SUMMARY] TELEGRAM VALIDATION METRICS")
    print("=" * 60)
    print(f" Validated (Active) : {validated_count}")
    print(f" Discarded          : {discarded_count}")
    print(f" Closed / 404       : {closed_count}")
    print("=" * 60 + "\n")


def run(limit: int | None = None) -> None:
    """Synchronous entry point."""
    asyncio.run(run_validator(limit=limit))
