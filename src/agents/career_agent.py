from playwright.async_api import async_playwright

from config import HEADLESS

from database.career_sources import (
    get_career_sources,
    mark_source_checked,
)

from core.career_source import (
    normalize_source_type,
)


class CareerAgent:

    async def run(self):

        sources = get_career_sources()

        if not sources:

            print(
                "No career sources configured."
            )

            return

        print(
            f"Found {len(sources)} career sources."
        )

        playwright = None
        browser = None

        try:

            playwright = (
                await async_playwright().start()
            )

            browser = (
                await playwright.chromium.launch(
                    headless=HEADLESS
                )
            )

            for index, source in enumerate(
                sources,
                start=1,
            ):

                await self.check_source(
                    source,
                    index,
                    len(sources),
                    playwright,
                    browser,
                )

        finally:

            if browser:
                await browser.close()

            if playwright:
                await playwright.stop()


    async def check_source(
        self,
        source,
        index,
        total,
        playwright,
        browser,
    ):

        source_id = source["id"]
        company = source["company"]
        url = source["careers_url"]

        print()
        print(
            f"[{index}/{total}] {company}"
        )

        print(
            f"URL: {url}"
        )

        page = None

        try:

            page = await browser.new_page()

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            if response:

                print(
                    f"HTTP status: "
                    f"{response.status}"
                )

            print(
                f"Final URL: "
                f"{page.url}"
            )

            title = await page.title()

            print(
                f"Page title: {title}"
            )

            body = (
                await page.locator(
                    "body"
                ).inner_text()
            )

            job_links = await page.locator(
                "a[href*='/job'], "
                "a[href*='/jobs'], "
                "a[href*='/vaga'], "
                "a[href*='/vagas'], "
                "a[href*='/careers']"
            ).count()

            print(
                f"Possible job links: "
                f"{job_links}"
            )

            source_type = (
                self.detect_source_type(
                    page.url,
                    body,
                )
            )

            print(
                f"Source type: "
                f"{source_type}"
            )

            mark_source_checked(
                source_id,
                success=True,
            )

        except Exception as error:

            print(
                f"ERROR: {error}"
            )

            mark_source_checked(
                source_id,
                success=False,
                error=str(error),
            )

        finally:

            if page:

                await page.close()


    @staticmethod
    def detect_source_type(
        url: str,
        body: str,
    ) -> str:

        value = (
            f"{url} {body}"
        ).lower()

        if "gupy" in value:
            return "GUPY"

        if "pandape" in value:
            return "PANDAPE"

        if "quickin" in value:
            return "QUICKIN"

        if "kenoby" in value:
            return "KENOBY"

        if "vagas.com" in value:
            return "VAGAS"

        if "enter.jobs" in value:
            return "ENTER"

        if "linkedin.com" in value:
            return "LINKEDIN"

        return normalize_source_type(
            "GENERIC"
        )