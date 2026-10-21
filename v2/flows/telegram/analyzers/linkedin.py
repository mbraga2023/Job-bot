"""LinkedIn Page Analyzer for v2."""

from __future__ import annotations

import re
from urllib.parse import urljoin
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class LinkedInAnalyzer:
    """Extracts job application status, remote eligibility, and direct apply link from LinkedIn."""

    async def get_application_url(self, page: Page) -> str:
        """Return the href of an application link if LinkedIn exposes one."""
        locator = page.get_by_role(
            "link",
            name=re.compile(r"\bapply\b|candidate-se agora", re.IGNORECASE),
        ).first
        try:
            if await locator.count():
                href = await locator.get_attribute("href")
                if href:
                    return urljoin(page.url, href)
        except Exception:
            pass
        return ""

    async def analyze(self, page: Page) -> dict:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except PlaywrightTimeoutError:
            pass

        try:
            await page.wait_for_selector("a[href*='/jobs/view/']", timeout=15_000)
        except PlaywrightTimeoutError:
            pass

        await page.wait_for_timeout(2_000)

        try:
            body = await page.locator("body").inner_text(timeout=10_000)
        except Exception:
            body = ""

        normalized_body = self._normalize(body)

        if self._is_closed(normalized_body):
            return self._result(applications_open=False, remote=None, status="CLOSED")

        workplace = await self._detect_workplace(page=page, body=normalized_body)
        easy_apply = await self._has_easy_apply(page)

        if workplace == "NOT_REMOTE":
            return self._result(applications_open=True, remote=False, status="NOT_REMOTE", easy_apply=easy_apply)

        if workplace == "REMOTE":
            return self._result(applications_open=True, remote=True, status="OPEN", easy_apply=easy_apply)

        return self._result(applications_open=True, remote=True, status="OPEN", easy_apply=easy_apply)

    async def _has_easy_apply(self, page: Page) -> bool:
        button_name = re.compile(r"\beasy apply\b", re.IGNORECASE)
        selectors = (
            ".job-details-jobs-unified-top-card__container--two-pane",
            ".jobs-unified-top-card",
        )
        for selector in selectors:
            try:
                sections = page.locator(selector)
                section_count = await sections.count()
            except Exception:
                continue

            for section_index in range(section_count):
                section = sections.nth(section_index)
                try:
                    buttons = section.get_by_role("button", name=button_name)
                    button_count = await buttons.count()
                except Exception:
                    continue

                for button_index in range(button_count):
                    try:
                        if await buttons.nth(button_index).is_visible():
                            return True
                    except Exception:
                        continue

        buttons = page.locator('button[aria-label*="Easy Apply" i]')
        for button_index in range(await buttons.count()):
            if await buttons.nth(button_index).is_visible():
                return True

        return False

    @staticmethod
    def _is_closed(body: str) -> bool:
        closed_markers = (
            "unable to load the page",
            "no longer accepting applications",
            "no longer accepting applicants",
            "not currently accepting applications",
            "not accepting applications",
            "applications are closed",
            "application period has ended",
            "não está mais aceitando candidaturas",
            "não aceita mais candidaturas",
            "nao esta mais aceitando candidaturas",
            "nao aceita mais candidaturas",
            "vaga encerrada",
            "candidaturas encerradas",
            "inscrições encerradas",
            "inscricoes encerradas",
        )
        return any(marker in body for marker in closed_markers)

    async def _detect_workplace(self, page: Page, body: str) -> str | None:
        workplace = page.locator("a[href*='/jobs/view/']")
        count = await workplace.count()

        for index in range(count):
            try:
                text = await workplace.nth(index).inner_text(timeout=2_000)
            except Exception:
                continue
            detected = self._classify_workplace(self._normalize(text))
            if detected:
                return detected

        selectors = ("[data-test-job-details]", "[data-testid*='job-details']", "li", "div", "span")
        for selector in selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
            except Exception:
                continue

            limit = min(count, 500)
            for index in range(limit):
                try:
                    text = await elements.nth(index).inner_text(timeout=500)
                except Exception:
                    continue
                normalized = self._normalize(text)
                if len(normalized) > 300:
                    continue
                detected = self._classify_workplace(normalized)
                if detected:
                    return detected

        not_remote_markers = ("on-site", "on site", "onsite", "presencial", "hybrid", "híbrido", "hibrido")
        for marker in not_remote_markers:
            if self._contains_workplace_marker(body, marker):
                return "NOT_REMOTE"

        remote_markers = ("remote", "remoto", "remota", "work from home", "home office")
        for marker in remote_markers:
            if self._contains_workplace_marker(body, marker):
                return "REMOTE"

        return None

    @classmethod
    def _classify_workplace(cls, text: str) -> str | None:
        if not text:
            return None
        not_remote_patterns = (r"\bon[- ]site\b", r"\bonsite\b", r"\bhybrid\b", r"\bpresencial\b", r"\bhíbrido\b", r"\bhibrido\b")
        for pattern in not_remote_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return "NOT_REMOTE"

        remote_patterns = (r"\bremote\b", r"\bremoto\b", r"\bremota\b", r"\bwork from home\b", r"\bhome office\b")
        for pattern in remote_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return "REMOTE"

        return None

    @staticmethod
    def _contains_workplace_marker(body: str, marker: str) -> bool:
        pattern = r"(?<!\w)" + re.escape(marker) + r"(?!\w)"
        return bool(re.search(pattern, body, flags=re.IGNORECASE))

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.casefold().replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _result(applications_open: bool, remote: bool | None, status: str, easy_apply: bool = False) -> dict:
        return {
            "job_source": "LINKEDIN",
            "applications_open": applications_open,
            "remote": remote,
            "job_status": status,
            "easy_apply": easy_apply,
        }
