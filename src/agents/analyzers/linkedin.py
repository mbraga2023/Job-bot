#agents/analysers/linkedin.py
from playwright.async_api import Page


class LinkedInAnalyzer:

    async def analyze(self, page: Page) -> dict:

        body = (
            await page.locator("body").inner_text()
        ).lower()

        closed = any(
            text in body
            for text in (
                "no longer accepting applications",
                "não está mais aceitando candidaturas",
                "não aceita mais candidaturas",
            )
        )

        return {
            "job_source": "LINKEDIN",
            "applications_open": not closed,
            "job_status": "CLOSED" if closed else "OPEN",
        }