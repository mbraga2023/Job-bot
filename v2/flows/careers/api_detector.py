"""Career Page API Detector for v2."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from playwright.async_api import Page, async_playwright

from v2.config import config
from v2.core.database import get_active_career_sources, update_source_api_info


class CareerApiDetector:
    """Sniffs network responses while browsing a career page to find JSON API endpoints."""

    JOB_PATTERNS = {
        r"/jobs?([/?]|$)": 10,
        r"/vagas?([/?]|$)": 10,
        r"/vacanc(y|ies)([/?]|$)": 10,
        r"/opportunit(y|ies)([/?]|$)": 10,
        r"/positions?([/?]|$)": 8,
        r"/openings?([/?]|$)": 8,
        r"/careers?([/?]|$)": 5,
        r"/search([/?]|$)": 8,
        r"/job[_-]?search": 15,
        r"/searchjobs": 15,
        r"/jobboard": 10,
    }

    IGNORE_PATTERNS = {
        r"linkedin\.com": -30,
        r"googleads": -30,
        r"doubleclick": -30,
        r"analytics": -25,
        r"tracking": -25,
        r"consent": -20,
        r"captcha": -30,
        r"login": -15,
    }

    async def detect_api(self, page: Page, url: str) -> dict[str, Any] | None:
        detected_candidates: list[dict[str, Any]] = []

        async def on_response(response):
            try:
                ct = response.headers.get("content-type", "")
                if "application/json" not in ct:
                    return
                req = response.request
                resp_url = req.url
                score = 0
                for pattern, weight in self.JOB_PATTERNS.items():
                    if re.search(pattern, resp_url, re.IGNORECASE):
                        score += weight
                for pattern, penalty in self.IGNORE_PATTERNS.items():
                    if re.search(pattern, resp_url, re.IGNORECASE):
                        score += penalty

                if score > 0:
                    detected_candidates.append(
                        {
                            "url": resp_url,
                            "method": req.method,
                            "score": score,
                        }
                    )
            except Exception:
                pass

        page.on("response", on_response)
        try:
            await page.goto(url, wait_until="networkidle", timeout=config.timeout_ms)
        except Exception:
            pass

        if not detected_candidates:
            return None

        # Return highest scored candidate
        detected_candidates.sort(key=lambda c: c["score"], reverse=True)
        return detected_candidates[0]


async def run_detector(limit: int = 500) -> None:
    """Scan active career sources that lack API endpoints and sniff for them."""
    sources = get_active_career_sources()
    pending = [s for s in sources if not s.get("api_url")][:limit]

    if not pending:
        print("[INFO] No pending career sources need API detection.")
        return

    print(f"\n[INFO] Sniffing API endpoints for {len(pending)} career sources...\n")
    detector = CareerApiDetector()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=config.headless)
        page = await browser.new_page()

        for s in pending:
            print(f" Checking {s['company']} ({s['careers_url']})...")
            found = await detector.detect_api(page, s["careers_url"])
            if found:
                print(
                    f"  [+] Found API: {found['method']} {found['url']} (Score: {found['score']})"
                )
                update_source_api_info(
                    s["id"], api_url=found["url"], api_method=found["method"]
                )
            else:
                print("  [-] No JSON job API detected.")

        await browser.close()


def run(limit: int = 500) -> None:
    """Synchronous entry point."""
    asyncio.run(run_detector(limit=limit))
