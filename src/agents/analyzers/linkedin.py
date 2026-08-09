#agents/analysers/linkedin.py
from playwright.async_api import Page


CLOSED_MARKERS = (
    "no longer accepting applications",
    "não está mais aceitando candidaturas",
    "não aceita mais candidaturas",
    "vaga encerrada",
    "vaga fechada",
)


NOT_REMOTE_MARKERS = (
    "hybrid",
    "híbrido",
    "hibrido",
    "on-site",
    "onsite",
    "on site",
    "presencial",
)


class LinkedInAnalyzer:

    async def analyze(self, page: Page) -> dict:

        body = (
            await page.locator("body")
            .inner_text()
        ).lower()

        # -----------------------------------------
        # Check if vacancy is closed
        # -----------------------------------------

        closed = any(
            text in body
            for text in CLOSED_MARKERS
        )

        if closed:

            return {
                "job_source": "LINKEDIN",
                "applications_open": False,
                "remote": False,
                "job_status": "CLOSED",
            }

        # -----------------------------------------
        # Check if job is NOT remote
        # -----------------------------------------

        not_remote = any(
            text in body
            for text in NOT_REMOTE_MARKERS
        )

        if not_remote:

            return {
                "job_source": "LINKEDIN",
                "applications_open": True,
                "remote": False,
                "job_status": "NOT_REMOTE",
            }

        # -----------------------------------------
        # Job is open and remote
        # -----------------------------------------

        return {
            "job_source": "LINKEDIN",
            "applications_open": True,
            "remote": True,
            "job_status": "OPEN",
        }