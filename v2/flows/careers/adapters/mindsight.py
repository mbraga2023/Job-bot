"""Mindsight Candidate Portal Adapter for v2."""

from __future__ import annotations

from urllib.parse import urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from v2.core.keywords import is_qa_job_title, normalize_job_title
from v2.flows.careers.adapters.base import (
    BaseCareerAdapter,
    CareerJobItem,
    CareerPageModel,
)

MINDSIGHT_MODEL = CareerPageModel(
    platform="mindsight",
    search_input=['input[placeholder="Search job title"]'],
    search_button=["button.ant-input-search-button"],
    job_links=['a[href*="/supernova/"]'],
    job_cards=[".ant-card"],
    next_page=["li.ant-pagination-next button"],
)


class MindsightAdapter(BaseCareerAdapter):
    """Adapter for Mindsight's candidate opportunity portals."""

    def __init__(self, page: Page):
        super().__init__(page, MINDSIGHT_MODEL)

    async def wait_for_page_ready(self) -> None:
        try:
            await self.page.locator(self.model.job_links[0]).first.wait_for(
                state="visible",
                timeout=12_000,
            )
        except PlaywrightTimeoutError:
            pass

    async def search(self, term: str) -> bool:
        for selector in self.model.search_input:
            locator = self.page.locator(selector).first
            try:
                if not await locator.is_visible(timeout=1500):
                    continue
                await locator.fill(term)
                await self.page.locator(self.model.search_button[0]).click()
                return True
            except PlaywrightTimeoutError:
                continue
        return False

    async def get_jobs(self, company_name: str | None = None) -> list[CareerJobItem]:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PlaywrightTimeoutError:
            pass

        jobs: list[CareerJobItem] = []
        seen_urls: set[str] = set()
        links = self.page.locator(self.model.job_links[0])

        while True:
            elements = await links.evaluate_all(
                """links => links.map(link => {
                    const card = link.closest('.ant-card');
                    const text = element => (element?.innerText || element?.textContent || "")
                        .replace(/\\s+/g, " ").trim();
                    return {
                        url: link.href,
                        title: text(card?.querySelector("h5")) || text(link),
                        location: text(card?.querySelector("i"))
                    };
                })"""
            )

            for element in elements:
                url = element["url"].strip()
                title = normalize_job_title(element["title"])
                if (
                    not url
                    or url in seen_urls
                    or not is_qa_job_title(title)
                ):
                    continue

                seen_urls.add(url)
                jobs.append(
                    CareerJobItem(
                        title=title,
                        url=url,
                        company=company_name,
                        location=element["location"] or None,
                        external_id=urlparse(url).path.rstrip("/").rsplit("/", 1)[-1],
                    )
                )

            next_page = self.page.locator(self.model.next_page[0])
            if await next_page.is_disabled():
                break

            active_page = self.page.locator(".ant-pagination-item-active")
            active_page_number = await active_page.get_attribute("title")
            if not active_page_number:
                break

            await next_page.click()
            await self.page.wait_for_function(
                """previous => {
                    const active = document.querySelector(".ant-pagination-item-active");
                    return active && active.getAttribute("title") !== previous;
                }""",
                arg=active_page_number,
                timeout=5_000,
            )

        return jobs
