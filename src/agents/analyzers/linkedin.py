# agents/analyzers/linkedin.py

import re

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class LinkedInAnalyzer:

    async def analyze(self, page: Page) -> dict:
        """
        Status priority:
        1. CLOSED
        2. NOT_REMOTE
        3. OPEN
        """

        await page.wait_for_load_state(
            "domcontentloaded",
            timeout=15_000,
        )

        # Wait for LinkedIn's job content to render.
        try:
            await page.wait_for_selector(
                "a[href*='/jobs/view/']",
                timeout=15_000,
            )
        except PlaywrightTimeoutError:
            pass

        # LinkedIn inserts the workplace label asynchronously.
        await page.wait_for_timeout(2_000)

        body = await page.locator("body").inner_text(
            timeout=10_000
        )

        body = self._normalize(body)

        closed_markers = (
            "no longer accepting applications",
            "não está mais aceitando candidaturas",
            "não aceita mais candidaturas",
            "vaga encerrada",
            "candidaturas encerradas",
        )

        if any(marker in body for marker in closed_markers):
            return self._result(
                applications_open=False,
                remote=None,
                status="CLOSED",
            )

        # Check the actual rendered workplace label directly.
        workplace = page.locator(
            "a[href*='/jobs/view/']"
        ).filter(
            has_text=re.compile(
                r"^\s*(on-site|on site|onsite|hybrid|"
                r"presencial|híbrido|hibrido)\s*$",
                re.IGNORECASE,
            )
        )

        if await workplace.count() > 0:
            return self._result(
                applications_open=True,
                remote=False,
                status="NOT_REMOTE",
            )

        # Fallback to body text.
        not_remote_markers = (
            "on-site",
            "on site",
            "onsite",
            "presencial",
            "hybrid",
            "híbrido",
            "hibrido",
        )

        if any(marker in body for marker in not_remote_markers):
            return self._result(
                applications_open=True,
                remote=False,
                status="NOT_REMOTE",
            )

        print(
            "Workplace type was not found:",
            f"url={page.url}",
            f"title={await page.title()}",
        )

        return self._result(
            applications_open=True,
            remote=True,
            status="OPEN",
        )

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.casefold()
        value = value.replace("\u2011", "-")
        value = value.replace("\u2013", "-")
        value = value.replace("\u2014", "-")
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _result(
        applications_open: bool,
        remote: bool | None,
        status: str,
    ) -> dict:
        return {
            "job_source": "LINKEDIN",
            "applications_open": applications_open,
            "remote": remote,
            "job_status": status,
        }
