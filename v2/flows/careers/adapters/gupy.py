"""Gupy Career Portal Adapter for v2."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from v2.flows.careers.adapters.base import BaseCareerAdapter, CareerJobItem, CareerPageModel

GUPY_MODEL = CareerPageModel(
    platform="gupy",
    search_input=[
        'input[data-testid="search-input"]',
        'input[placeholder*="Buscar vaga" i]',
        'input[placeholder*="Search" i]',
        'input[type="search"]',
    ],
    search_button=[
        'button[data-testid="search-button"]',
        'button[type="submit"]',
    ],
    job_links=[
        'a[href*="/job/"]',
        'a[href*="/jobs/"]',
        'a[data-testid="job-card-link"]',
    ],
    job_cards=['li[data-testid="job-card"]', 'div[data-testid="job-card"]'],
    next_page=['button[aria-label*="Next" i]', 'button[aria-label*="Próxima" i]'],
)


class GupyAdapter(BaseCareerAdapter):
    """Adapter for crawling Gupy career portals."""

    def __init__(self, page: Page):
        super().__init__(page, GUPY_MODEL)

    async def get_jobs(self, company_name: str | None = None) -> list[CareerJobItem]:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=8_000)
        except PlaywrightTimeoutError:
            pass

        # Scroll to load listings
        for _ in range(5):
            await self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(500)

        links = await self.get_job_links()
        jobs: list[CareerJobItem] = []
        seen: set[str] = set()

        for link in links:
            # Filter valid Gupy job link
            if not re.search(r"/(?:job|jobs)/\d+", link):
                continue
            if link in seen:
                continue
            seen.add(link)

            # Try to grab title from element or path
            jobs.append(CareerJobItem(
                title="",
                url=link,
                company=company_name,
            ))

        return jobs
