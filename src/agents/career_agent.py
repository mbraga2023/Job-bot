from urllib.parse import urlparse

from playwright.async_api import async_playwright

from config import HEADLESS

from agents.analyzers.career import CareerAnalyzer
from agents.platforms.inhire import InHireAdapter
from core.career_result import CareerScanResult

from database.career_jobs import (
    deactivate_missing_jobs,
    insert_career_job,
)

from database.career_sources import (
    get_career_sources,
    mark_source_checked,
    update_career_source_status,
)


class CareerAgent:
    """
    Scans configured career pages for QA-related jobs.

    Workflow:
    1. Open the career page.
    2. Find visible job links.
    3. Keep QA-related jobs.
    4. If none are found, search for QA when a search input exists.
    5. Save matching jobs in career_jobs.
    6. Mark previously found jobs as inactive when they disappear.
    """

    def __init__(self, platform="search_all"):
        if platform not in {"search_all", "inhire"}:
            raise ValueError(f"Unsupported career platform: {platform}")
        self.platform = platform
        self.analyzer = CareerAnalyzer()

    async def run(self):
        sources = get_career_sources(active_only=True)
        if self.platform == "inhire":
            sources = [
                source
                for source in sources
                if self.is_inhire_source(source["careers_url"])
            ]

        if not sources:
            if self.platform == "inhire":
                print("No InHire career sources configured.")
            else:
                print("No career sources configured.")
            return

        print(
            f"Found {len(sources)} "
            f"{'InHire ' if self.platform == 'inhire' else ''}career sources."
        )

        playwright = None
        browser = None

        try:
            playwright = await async_playwright().start()

            browser = await playwright.chromium.launch(
                headless=HEADLESS,
            )

            for index, source in enumerate(
                sources,
                start=1,
            ):
                await self.check_source(
                    source=source,
                    index=index,
                    total=len(sources),
                    browser=browser,
                )

        finally:
            if browser:
                await browser.close()

            if playwright:
                await playwright.stop()

    async def check_source(
        self,
        source,
        index: int,
        total: int,
        browser,
    ):
        source_id = source["id"]
        company = source["company"]
        source_url = source["careers_url"]

        print()
        print(f"[{index}/{total}] {company}")
        print(f"URL: {source_url}")

        page = None

        try:
            page = await browser.new_page()

            response = await page.goto(
                source_url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )

            if response:
                print(f"HTTP status: {response.status}")

                if response.status >= 400:
                    raise RuntimeError(
                        f"HTTP error {response.status}"
                    )

            print(f"Final URL: {page.url}")
            print(f"Page title: {await page.title()}")

            if self.platform == "inhire":
                result = await self.analyze_inhire_page(page)
            else:
                result = await self.analyzer.analyze(
                    page=page,
                    source_url=source_url,
                )

            print(f"Result: {result.message}")
            print(f"QA jobs found: {len(result.jobs)}")

            active_urls = []

            for job in result.jobs:
                active_urls.append(job.url)

                insert_career_job(
                    career_source_id=source_id,
                    title=job.title,
                    company=job.company or company,
                    location=job.location,
                    url=job.url,
                    external_id=None,
                    published_date=None,
                    raw_data=job.raw_data,
                )

                print(f"  ✓ {job.title}")
                print(f"    {job.url}")

            # This assumes career_jobs contains only QA jobs.
            # If you later save all jobs, change this logic so that
            # non-QA jobs are not deactivated.
            if result.jobs:
                deactivate_missing_jobs(
                    career_source_id=source_id,
                    active_urls=active_urls,
                )
            else:
                print(
                    "No jobs extracted; skipping deactivation "
                    "to protect existing records."
                )

            body = await page.locator("body").inner_text()

            source_type = self.detect_source_type(
                url=page.url,
                body=body,
            )

            update_career_source_status(
                source_id=source_id,
                source_type=source_type,
                discovered_jobs=len(result.jobs),
            )

            mark_source_checked(
                source_id=source_id,
                success=True,
            )

        except Exception as error:
            print(f"ERROR: {error}")

            mark_source_checked(
                source_id=source_id,
                success=False,
                error=str(error),
            )

        finally:
            if page:
                await page.close()

    @staticmethod
    def is_inhire_source(url: str) -> bool:
        hostname = (urlparse(url).hostname or "").casefold()
        return hostname == "inhire.app" or hostname.endswith(".inhire.app")

    async def analyze_inhire_page(self, page):
        adapter = InHireAdapter(page)
        await adapter.wait_for_page_ready()
        page_jobs = await adapter.get_jobs()
        jobs = self.analyzer._filter_qa_jobs(page_jobs)
        print(
            f"    InHire page scan: {len(page_jobs)} job(s) loaded; "
            f"{len(jobs)} QA job(s) matched locally."
        )

        return CareerScanResult(
            success=True,
            page_good=True,
            jobs=jobs,
            message=(
                f"Found {len(jobs)} InHire QA job(s) "
                "by scanning the loaded job listings."
            ),
        )

    @staticmethod
    def detect_source_type(
        url: str,
        body: str,
    ) -> str:
        value = f"{url} {body}".casefold()

        source_types = (
            ("inhire", "INHIRE"),
            ("gupy", "GUPY"),
            ("pandape", "PANDAPE"),
            ("quickin", "QUICKIN"),
            ("kenoby", "KENOBY"),
            ("vagas.com", "VAGAS"),
            ("enter.jobs", "ENTER"),
            ("greenhouse", "GREENHOUSE"),
            ("lever.co", "LEVER"),
            ("workday", "WORKDAY"),
            ("myworkdayjobs", "WORKDAY"),
            ("ashbyhq", "ASHBY"),
            ("smartrecruiters", "SMARTRECRUITERS"),
            ("teamtailor", "TEAMTAILOR"),
            ("recruitee", "RECRUITEE"),
            ("linkedin.com", "LINKEDIN"),
        )

        for marker, source_type in source_types:
            if marker in value:
                return source_type

        return "GENERIC"


async def main():
    agent = CareerAgent()
    await agent.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
