from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse

from agents.platforms.base import (
    BaseCareerAdapter,
    CareerPageModel,
)
from core.career_result import CareerJob

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
    def __init__(self, page):
        super().__init__(page, INHIRE_MODEL)

    async def wait_for_page_ready(self):
        try:
            await self.page.locator(self.model.job_links[0]).first.wait_for(
                state="visible",
                timeout=15_000,
            )
        except PlaywrightTimeoutError:
            pass

    async def get_jobs(self) -> list[CareerJob]:
        links = self.page.locator(self.model.job_links[0])
        previous_state = None
        stable_rounds = 0
        fully_loaded = False

        for _ in range(30):
            await self.page.evaluate(
                "() => window.scrollTo(0, document.body.scrollHeight)"
            )
            await self.page.wait_for_timeout(750)
            current_state = (
                await links.count(),
                await self.page.evaluate("() => document.body.scrollHeight"),
            )

            if current_state == previous_state:
                stable_rounds += 1
                if stable_rounds >= 3:
                    fully_loaded = True
                    break
            else:
                stable_rounds = 0

            previous_state = current_state

        if not fully_loaded:
            print(
                "    WARNING: InHire job list kept changing while scrolling; "
                "the mapped results may be incomplete."
            )

        elements = await links.evaluate_all(
            """links => links.map(link => ({
                url: link.href,
                title: (link.innerText || link.textContent || "").trim(),
                visible: link.getClientRects().length > 0
                    && getComputedStyle(link).visibility !== "hidden"
            }))"""
        )
        jobs = []
        seen_urls = set()

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
            jobs.append(CareerJob(title=title, url=url))

        return jobs
