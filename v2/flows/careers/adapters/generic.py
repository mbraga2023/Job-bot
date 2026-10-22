"""Generic Career Portal Adapter for v2."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from v2.flows.careers.adapters.base import BaseCareerAdapter, CareerJobItem, CareerPageModel
from v2.core.keywords import is_qa_job_title, normalize_job_title

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

    @staticmethod
    def _is_job_detail_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False

        path = parsed.path.rstrip("/").lower()
        job_path = re.search(
            r"/(?:jobs?|positions?|vacanc(?:y|ies)|openings?|requisitions?|"
            r"apply|vagas?|careers?)/[^/]+$",
            path,
        )
        query = {key.lower(): values for key, values in parse_qs(parsed.query).items()}
        has_job_id = any(
            key in query for key in ("gh_jid", "jobid", "job_id", "jobid%3d")
        )
        return bool(job_path or has_job_id)

    @staticmethod
    def _title_from_url(url: str) -> str:
        slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        if slug.isdigit() or not slug:
            return ""
        title = normalize_job_title(re.sub(r"[-_]+", " ", slug)).title()
        return re.sub(r"\bQa\b", "QA", title)

    async def get_jobs(self, company_name: str | None = None) -> list[CareerJobItem]:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PlaywrightTimeoutError:
            pass

        jobs: list[CareerJobItem] = []
        seen: set[str] = set()

        for element in await self.get_job_link_details():
            url = element["url"]
            if url in seen or not self._is_job_detail_url(url):
                continue
            title = normalize_job_title(element["title"]) or self._title_from_url(url)
            if not is_qa_job_title(title):
                continue

            seen.add(url)
            jobs.append(CareerJobItem(
                title=title,
                url=url,
                company=company_name,
            ))

        return jobs
