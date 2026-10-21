"""Generic Career Portal Adapter for v2."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from v2.flows.careers.adapters.base import BaseCareerAdapter, CareerJobItem, CareerPageModel

GENERIC_MODEL = CareerPageModel(
    platform="generic",
    search_input=[
        'input[type="search"]',
        'input[name*="search" i]',
        'input[name*="q" i]',
        'input[placeholder*="search" i]',
        'input[placeholder*="buscar" i]',
        'input[placeholder*="vaga" i]',
    ],
    search_button=[
        'button[type="submit"]',
        'button[aria-label*="search" i]',
        'button:has-text("Search")',
        'button:has-text("Buscar")',
    ],
    job_links=[
        'a[href*="/vaga/"]',
        'a[href*="/vagas/"]',
        'a[href*="/job/"]',
        'a[href*="/jobs/"]',
        'a[href*="/career/"]',
        'a[href*="/careers/"]',
        'a[href*="/positions/"]',
        'a[href*="/oportunidade/"]',
        'a[href*="/oportunidades/"]',
        'a[href*="greenhouse.io"]',
        'a[href*="lever.co"]',
        'a[href*="workable.com"]',
    ],
    job_cards=['.job-item', '.job-card', '[data-job-id]'],
    next_page=['a[rel="next"]', 'button:has-text("Next")', 'button:has-text("Próxima")'],
)


class GenericAdapter(BaseCareerAdapter):
    """Fallback adapter for generic company career pages."""

    def __init__(self, page: Page):
        super().__init__(page, GENERIC_MODEL)

    async def get_jobs(self, company_name: str | None = None) -> list[CareerJobItem]:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PlaywrightTimeoutError:
            pass

        links = await self.get_job_links()
        jobs: list[CareerJobItem] = []
        seen: set[str] = set()

        for link in links:
            if link in seen:
                continue
            seen.add(link)
            jobs.append(CareerJobItem(
                title="",
                url=link,
                company=company_name,
            ))

        return jobs
