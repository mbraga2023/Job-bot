# agents/analyzers/linkedin.py
# agents/analyzers/linkedin.py

import re

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)


class LinkedInAnalyzer:

    async def analyze(self, page: Page) -> dict:
        """
        LinkedIn job status rules:

        1. CLOSED
           Job is explicitly closed / no longer accepting applications.

        2. NOT_REMOTE
           Job is OPEN and explicitly marked as:
               - Hybrid
               - On-site
               - On site
               - Onsite
               - Presencial
               - Híbrido
               - Hibrido

        3. OPEN
           Job is OPEN and:
               - explicitly marked Remote
               - OR no workplace location tag was found

        Important:
            Absence of a Remote tag does NOT mean NOT_REMOTE.
            We only return NOT_REMOTE when Hybrid/On-site is
            explicitly detected.
        """

        # =================================================
        # Wait for LinkedIn page
        # =================================================

        try:
            await page.wait_for_load_state(
                "domcontentloaded",
                timeout=15_000,
            )
        except PlaywrightTimeoutError:
            pass

        # LinkedIn content is rendered asynchronously.
        try:
            await page.wait_for_selector(
                "a[href*='/jobs/view/']",
                timeout=15_000,
            )
        except PlaywrightTimeoutError:
            pass

        await page.wait_for_timeout(2_000)

        # =================================================
        # Get page text
        # =================================================

        try:
            body = await page.locator(
                "body"
            ).inner_text(
                timeout=10_000
            )
        except Exception:
            body = ""

        normalized_body = self._normalize(body)

        # =================================================
        # 1. CLOSED
        # =================================================

        if self._is_closed(normalized_body):

            print(
                f"[LINKEDIN] CLOSED: {page.url}"
            )

            return self._result(
                applications_open=False,
                remote=None,
                status="CLOSED",
            )

        # =================================================
        # 2. Detect workplace type
        # =================================================

        workplace = await self._detect_workplace(
            page=page,
            body=normalized_body,
        )

        # =================================================
        # 3. HYBRID / ON-SITE
        # =================================================

        if workplace == "NOT_REMOTE":

            print(
                "[LINKEDIN] OPEN but NOT_REMOTE:",
                page.url,
            )

            return self._result(
                applications_open=True,
                remote=False,
                status="NOT_REMOTE",
            )

        # =================================================
        # 4. REMOTE
        # =================================================

        if workplace == "REMOTE":

            print(
                "[LINKEDIN] OPEN + REMOTE:",
                page.url,
            )

            return self._result(
                applications_open=True,
                remote=True,
                status="OPEN",
            )

        # =================================================
        # 5. OPEN with no workplace tag
        # =================================================

        print(
            "[LINKEDIN] OPEN - no workplace tag:",
            page.url,
        )

        return self._result(
            applications_open=True,
            remote=True,
            status="OPEN",
        )

    # =====================================================
    # CLOSED
    # =====================================================

    @staticmethod
    def _is_closed(
        body: str,
    ) -> bool:

        closed_markers = (
            "no longer accepting applications",
            "no longer accepting applicants",
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

        return any(
            marker in body
            for marker in closed_markers
        )

    # =====================================================
    # Workplace detection
    # =====================================================

    async def _detect_workplace(
        self,
        page: Page,
        body: str,
    ) -> str | None:
        """
        Returns:

            REMOTE
            NOT_REMOTE
            None

        Important:
            We only return NOT_REMOTE when Hybrid/On-site
            is explicitly detected.

            If nothing is found, return None.
        """

        # -------------------------------------------------
        # First: inspect rendered LinkedIn elements.
        # -------------------------------------------------

        workplace = page.locator(
            "a[href*='/jobs/view/']"
        )

        count = await workplace.count()

        for index in range(count):

            try:
                text = await workplace.nth(
                    index
                ).inner_text(
                    timeout=2_000
                )
            except Exception:
                continue

            normalized = self._normalize(
                text
            )

            detected = self._classify_workplace(
                normalized
            )

            if detected:
                return detected

        # -------------------------------------------------
        # Second: inspect common LinkedIn selectors.
        #
        # LinkedIn changes these classes frequently,
        # therefore we intentionally avoid relying on
        # one specific generated class.
        # -------------------------------------------------

        selectors = (
            "[data-test-job-details]",
            "[data-testid*='job-details']",
            "li",
            "div",
            "span",
        )

        for selector in selectors:

            try:
                elements = page.locator(
                    selector
                )

                count = await elements.count()

            except Exception:
                continue

            # Avoid scanning an excessive number of nodes.
            limit = min(count, 500)

            for index in range(limit):

                try:
                    text = await elements.nth(
                        index
                    ).inner_text(
                        timeout=500
                    )
                except Exception:
                    continue

                normalized = self._normalize(
                    text
                )

                # Don't process huge containers.
                if len(normalized) > 300:
                    continue

                detected = self._classify_workplace(
                    normalized
                )

                if detected:
                    return detected

        # -------------------------------------------------
        # Third: body fallback.
        #
        # IMPORTANT:
        # We check NOT_REMOTE first.
        # -------------------------------------------------

        not_remote_markers = (
            "on-site",
            "on site",
            "onsite",
            "presencial",
            "hybrid",
            "híbrido",
            "hibrido",
        )

        for marker in not_remote_markers:

            if self._contains_workplace_marker(
                body,
                marker,
            ):

                return "NOT_REMOTE"

        # -------------------------------------------------
        # Explicit Remote
        # -------------------------------------------------

        remote_markers = (
            "remote",
            "remoto",
            "remota",
            "work from home",
            "home office",
        )

        for marker in remote_markers:

            if self._contains_workplace_marker(
                body,
                marker,
            ):

                return "REMOTE"

        # -------------------------------------------------
        # Nothing found
        # -------------------------------------------------

        return None

    # =====================================================
    # Classify workplace text
    # =====================================================

    @classmethod
    def _classify_workplace(
        cls,
        text: str,
    ) -> str | None:

        if not text:
            return None

        # -----------------------------------------------
        # NOT REMOTE
        # -----------------------------------------------

        not_remote_patterns = (
            r"\bon[- ]site\b",
            r"\bonsite\b",
            r"\bhybrid\b",
            r"\bpresencial\b",
            r"\bhíbrido\b",
            r"\bhibrido\b",
        )

        for pattern in not_remote_patterns:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                return "NOT_REMOTE"

        # -----------------------------------------------
        # REMOTE
        # -----------------------------------------------

        remote_patterns = (
            r"\bremote\b",
            r"\bremoto\b",
            r"\bremota\b",
            r"\bwork from home\b",
            r"\bhome office\b",
        )

        for pattern in remote_patterns:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                return "REMOTE"

        return None

    # =====================================================
    # Safe marker detection
    # =====================================================

    @staticmethod
    def _contains_workplace_marker(
        body: str,
        marker: str,
    ) -> bool:
        """
        Checks whether a workplace marker appears as
        a standalone term.

        This avoids false positives such as:

            "remote" inside another word.
        """

        pattern = (
            r"(?<!\w)"
            + re.escape(marker)
            + r"(?!\w)"
        )

        return bool(
            re.search(
                pattern,
                body,
                flags=re.IGNORECASE,
            )
        )

    # =====================================================
    # Normalize
    # =====================================================

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:

        value = value.casefold()

        value = value.replace(
            "\u2011",
            "-",
        )

        value = value.replace(
            "\u2013",
            "-",
        )

        value = value.replace(
            "\u2014",
            "-",
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

    # =====================================================
    # Result
    # =====================================================

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