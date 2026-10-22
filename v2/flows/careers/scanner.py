"""Career Pages Scanner for v2."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from v2.config import config
from v2.core.database import (
    get_active_career_sources,
    insert_discovered_job,
    mark_source_checked,
)
from v2.core.keywords import QA_SEARCH_TERMS, is_qa_related
from v2.flows.careers.adapters import GenericAdapter, GupyAdapter, InHireAdapter

NAVIGATION_ATTEMPTS = 3


def is_inhire_url(url: str) -> bool:
    """Check if URL points to an InHire portal."""
    domain = urlparse(url).netloc.lower()
    return "inhire.app" in domain or "inhire.link" in domain


def is_gupy_url(url: str) -> bool:
    """Check if URL points to a Gupy portal."""
    domain = urlparse(url).netloc.lower()
    return "gupy.io" in domain


def was_checked_within_24h(source: dict) -> bool:
    """Check if the source was already checked in the last 24 hours."""
    last_checked = source.get("last_checked_at")
    if not last_checked:
        return False
    try:
        dt = datetime.fromisoformat(str(last_checked).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        print(f"[WARN] Invalid last_checked_at for source {source.get('id')}: {last_checked}")
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return dt >= cutoff


async def navigate_to_source(page, url: str, timeout_ms: int) -> str:
    """Navigate to a source, retry transient DNS failures, and follow page redirects."""
    for attempt in range(1, NAVIGATION_ATTEMPTS + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return page.url
        except PlaywrightError as exc:
            error = str(exc)
            if "ERR_NAME_NOT_RESOLVED" in error and attempt < NAVIGATION_ATTEMPTS:
                delay = attempt
                print(
                    f"  [PAGE] DNS lookup failed; retrying in {delay}s "
                    f"(attempt {attempt + 1}/{NAVIGATION_ATTEMPTS}).",
                    flush=True,
                )
                await asyncio.sleep(delay)
                continue

            if "interrupted by another navigation" in error.lower():
                print(
                    "  [PAGE] The site started another navigation; waiting for "
                    "the redirected page to load...",
                    flush=True,
                )
                try:
                    await page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    raise exc

                await page.wait_for_timeout(500)
                final_url = page.url
                if final_url and final_url != "about:blank":
                    print(f"  [PAGE] Continuing with final URL: {final_url}", flush=True)
                    return final_url
            raise

    raise RuntimeError(f"Could not navigate to {url} after {NAVIGATION_ATTEMPTS} attempts")


async def run_scanner(platform: str = "search_all") -> dict[str, int]:
    """Scan company career pages using platform adapters and save discovered jobs."""
    sources = get_active_career_sources()

    if platform == "inhire":
        sources = [s for s in sources if is_inhire_url(s["careers_url"])]

    # Apply 24-hour rate limit
    eligible_sources = []
    skipped_count = 0
    for s in sources:
        if not s.get("last_error") and was_checked_within_24h(s):
            skipped_count += 1
        else:
            eligible_sources.append(s)

    if skipped_count:
        print(f"[INFO] Skipped {skipped_count} source(s) checked within the last 24 hours.")

    if not eligible_sources:
        print("[INFO] No career sources need scanning right now.")
        return {"discovered": 0, "sources": 0}

    print("\n" + "=" * 60)
    print(f"[SCAN] Scanning {len(eligible_sources)} career source(s)...")
    print("=" * 60)

    total_discovered = 0
    new_jobs_count = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=config.headless)
        page = await browser.new_page()

        for idx, source in enumerate(eligible_sources, start=1):
            url = source["careers_url"]
            company = source["company"]
            print(
                f"\n[{idx}/{len(eligible_sources)}] Scanning {company} ({url})...",
                flush=True,
            )

            try:
                print(f"  [PAGE] Opening {url}...", flush=True)
                final_url = await navigate_to_source(page, url, config.timeout_ms)
                if final_url != url:
                    print(f"  [PAGE] Source redirected to {final_url}", flush=True)
                inhire = is_inhire_url(final_url)
                if inhire:
                    adapter = InHireAdapter(page)
                elif is_gupy_url(final_url):
                    adapter = GupyAdapter(page)
                else:
                    adapter = GenericAdapter(page)

                print("  [PAGE] Page loaded; waiting for job listings...", flush=True)
                if hasattr(adapter, "wait_for_page_ready"):
                    await adapter.wait_for_page_ready()

                # Get initial jobs
                if inhire:
                    print("  [INHIRE] Reading the job list...", flush=True)
                jobs = await adapter.get_jobs(company_name=company)
                print(f"  [PAGE] Found {len(jobs)} job listing(s).", flush=True)

                # If no jobs or adapter supports searching, try searching QA terms
                if not jobs and hasattr(adapter, "search"):
                    for term in QA_SEARCH_TERMS[:2]:  # Try top terms (e.g. 'QA', 'Quality Assurance')
                        print(f"  [SEARCH] Searching for '{term}'...", flush=True)
                        searched = await adapter.search(term)
                        if not searched:
                            print(
                                f"  [SEARCH] Search field not available for '{term}'.",
                                flush=True,
                            )
                            continue

                        print(f"  [SEARCH] Search submitted for '{term}'.", flush=True)
                        await page.wait_for_timeout(2000)
                        jobs = await adapter.get_jobs(company_name=company)
                        print(
                            f"  [SEARCH] Found {len(jobs)} job listing(s) for '{term}'.",
                            flush=True,
                        )
                        if jobs:
                            break

                source_new = 0
                for item in jobs:
                    # Filter QA if title is already populated; otherwise keep for validator
                    if item.title and not is_qa_related(item.title):
                        continue

                    job_id = insert_discovered_job(
                        pipeline="CAREER_PAGE",
                        career_source_id=source["id"],
                        source_url=item.url,
                        title=item.title or None,
                        company=company,
                        location=item.location,
                        external_id=item.external_id,
                        published_date=item.published_date,
                        raw_data=item.raw_data,
                    )
                    if job_id:
                        source_new += 1
                        new_jobs_count += 1
                        print(f"  [+] Discovered: {item.title or 'Unknown'} -> {item.url}")

                total_discovered += len(jobs)
                mark_source_checked(source["id"], discovered_jobs=len(jobs))
                print(
                    f"  [OK] Checked. Found {len(jobs)} total ({source_new} new).",
                    flush=True,
                )

            except Exception as exc:
                print(f"  [!] Failed to scan {company}: {exc}", flush=True)
                mark_source_checked(source["id"], error=str(exc))

        await browser.close()

    print("\n" + "=" * 60)
    print("[SUMMARY] SCANNING METRICS")
    print("=" * 60)
    print(f" Sources scanned : {len(eligible_sources)}")
    print(f" Total jobs seen : {total_discovered}")
    print(f" New jobs added  : {new_jobs_count}")
    print("=" * 60 + "\n")

    return {"discovered": total_discovered, "new": new_jobs_count}


def run(platform: str = "search_all") -> None:
    """Synchronous entry point."""
    asyncio.run(run_scanner(platform=platform))
