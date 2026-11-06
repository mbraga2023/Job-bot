"""Conquest One Jobs portal adapter for v2."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from v2.core.keywords import is_qa_job_title, normalize_job_title
from v2.flows.careers.adapters.base import (
    BaseCareerAdapter,
    CareerJobItem,
    CareerPageModel,
)

CONQUESTONE_MODEL = CareerPageModel(
    platform="conquestone",
    search_input=["#vMATCHTEXT"],
    search_button=["#BTNSEARCHTEXT"],
    job_links=[
        '#GridjobsContainerDiv a[href*="jobboard.job.wpdetails.aspx"]',
    ],
    job_cards=["#GridjobsContainerDiv tr"],
    next_page=["#UCPAGINATIONBARContainer li.next a"],
)


class ConquestOneAdapter(BaseCareerAdapter):
    """Adapter for Conquest One's GeneXus job board."""

    def __init__(self, page: Page):
        super().__init__(page, CONQUESTONE_MODEL)

    async def wait_for_page_ready(self) -> None:
        try:
            await self.page.locator(self.model.job_links[0]).first.wait_for(
                state="visible",
                timeout=12_000,
            )
        except PlaywrightTimeoutError:
            pass

    async def search(self, term: str) -> bool:
        search_input = self.page.locator(self.model.search_input[0]).first
        try:
            if not await search_input.is_visible(timeout=1500):
                return False
            await search_input.fill(term)
            await self.page.locator(self.model.search_button[0]).click()
            return True
        except PlaywrightTimeoutError:
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
                    const row = link.closest("tr");
                    const cells = row?.querySelectorAll("td") || [];
                    const text = element => (element?.innerText || element?.textContent || "")
                        .replace(/\\s+/g, " ").trim();
                    return {
                        url: link.href,
                        title: text(link),
                        location: text(cells[1])
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

                query = parse_qs(urlparse(url).query)
                external_id = (query.get("id") or [None])[0]
                seen_urls.add(url)
                jobs.append(
                    CareerJobItem(
                        title=title,
                        url=url,
                        company=company_name,
                        location=element["location"] or None,
                        external_id=external_id,
                    )
                )

            next_page = self.page.locator("#UCPAGINATIONBARContainer li.next")
            if not await next_page.count():
                break
            next_class = await next_page.get_attribute("class") or ""
            if "disabled" in next_class.split():
                break

            active_page = self.page.locator("#UCPAGINATIONBARContainer li.active")
            if not await active_page.count():
                break
            active_page_number = (await active_page.inner_text()).strip()
            await self.page.locator(self.model.next_page[0]).click()
            await self.page.wait_for_function(
                """previous => {
                    const active = document.querySelector(
                        "#UCPAGINATIONBARContainer li.active"
                    );
                    return active && active.innerText.trim() !== previous;
                }""",
                arg=active_page_number,
                timeout=10_000,
            )

        return jobs
