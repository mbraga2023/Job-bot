"""InHire Career Portal Adapter for v2."""

from __future__ import annotations

from urllib.parse import urlparse
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from v2.flows.careers.adapters.base import BaseCareerAdapter, CareerJobItem, CareerPageModel

INHIRE_MODEL = CareerPageModel(
    platform="inhire",
    search_input=[
        "input#name",
        'input[name="name"]',
        'input[placeholder="Search by job name"]',
    ],
    search_button=[],
    job_links=['a[href^="/vagas/"]'],
    job_cards=['li:has(a[href^="/vagas/"])'],
    next_page=[],
)


class InHireAdapter(BaseCareerAdapter):
    """Adapter for crawling InHire career portals."""

    def __init__(self, page: Page):
        super().__init__(page, INHIRE_MODEL)

    async def wait_for_page_ready(self) -> None:
        try:
            await self.page.locator(self.model.job_links[0]).first.wait_for(
                state="visible",
                timeout=12_000,
            )
        except PlaywrightTimeoutError:
            pass

    async def get_jobs(self, company_name: str | None = None) -> list[CareerJobItem]:
        links = self.page.locator(self.model.job_links[0])
        previous_state = None
        stable_rounds = 0

        # Scroll to load dynamic list
        for _ in range(25):
            await self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(600)
            count = await links.count()
            height = await self.page.evaluate("() => document.body.scrollHeight")
            current_state = (count, height)

            if current_state == previous_state:
                stable_rounds += 1
                if stable_rounds >= 3:
                    break
            else:
                stable_rounds = 0

            previous_state = current_state

        elements = await links.evaluate_all(
            """links => links.map(link => ({
                url: link.href,
                title: (link.innerText || link.textContent || "").trim(),
                visible: link.getClientRects().length > 0 && getComputedStyle(link).visibility !== "hidden"
            }))"""
        )

        jobs: list[CareerJobItem] = []
        seen_urls: set[str] = set()

        for element in elements:
            url = element["url"]
            title = " ".join(element["title"].split())
            path_parts = urlparse(url).path.split("/")

            if (
                not element["visible"]
                or len(path_parts) < 4
                or path_parts[1] != "vagas"
                or not title
                or title.casefold() in {"jobs", "vagas", "see the jobs", "ver vagas"}
                or url in seen_urls
            ):
                continue

            seen_urls.add(url)
            jobs.append(CareerJobItem(title=title, url=url, company=company_name))

        return jobs
