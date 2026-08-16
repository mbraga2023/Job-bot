# agents/analyzers/career.py

import re
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from core.career_result import (
    CareerJob,
    CareerScanResult,
)

from database.career_jobs import (
    insert_career_job,
    deactivate_missing_jobs,
)

from database.career_sources import (
    mark_source_checked,
    update_career_source_status,
)


class CareerAnalyzer:

    # =========================================================
    # SEARCH TERMS
    # =========================================================

    SEARCH_TERMS = (
        "QA",
        "Test",
        "Teste",
    )

    # =========================================================
    # QA / TEST RELEVANCE
    # =========================================================

    QA_PATTERN = re.compile(
        r"""
        (?:
            \bqa\b
            |
            quality[\s_-]+assurance
            |
            quality[\s_-]+analyst
            |
            quality[\s_-]+engineer
            |
            test[\s_-]+engineer
            |
            software[\s_-]+tester
            |
            software[\s_-]+testing
            |
            test[\s_-]+automation
            |
            automation[\s_-]+test
            |
            test[\s_-]+analyst
            |
            testing[\s_-]+analyst
            |
            tester
            |
            testing
            |
            analista[\s_-]+de[\s_-]+testes
            |
            analista[\s_-]+de[\s_-]+qualidade
            |
            analista[\s_-]+da[\s_-]+qualidade
            |
            analista[\s_-]+qualidade
            |
            engenheiro[\s_-]+de[\s_-]+testes
            |
            engenharia[\s_-]+de[\s_-]+qualidade
            |
            engenharia[\s_-]+de[\s_-]+testes
            |
            testes[\s_-]+de[\s_-]+software
            |
            automa(?:ç|c)[aã]o[\s_-]+de[\s_-]+testes
            |
            automatizador[\s_-]+de[\s_-]+testes
            |
            automation[\s_-]+engineer
            |
            test[\s_-]+automation[\s_-]+engineer
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # =========================================================
    # SEARCH INPUTS
    # =========================================================

    SEARCH_SELECTORS = (
        "input[type='search']",

        "input[name='q']",
        "input[name*='search' i]",
        "input[name*='buscar' i]",
        "input[name*='pesquis' i]",

        "input[name*='jobsearch' i]",
        "input[name*='job_search' i]",
        "input[name*='keyword' i]",
        "input[name*='keywords' i]",
        "input[name*='query' i]",

        "input[id='q' i]",
        "input[id*='search' i]",
        "input[id*='buscar' i]",
        "input[id*='pesquis' i]",
        "input[id*='job-search' i]",
        "input[id*='jobsearch' i]",
        "input[id*='keyword' i]",

        "input[placeholder*='search jobs' i]",
        "input[placeholder*='search job' i]",
        "input[placeholder*='search' i]",

        "input[placeholder*='buscar vagas' i]",
        "input[placeholder*='buscar empregos' i]",
        "input[placeholder*='buscar' i]",

        "input[placeholder*='pesquisar vagas' i]",
        "input[placeholder*='pesquisar empregos' i]",
        "input[placeholder*='pesquisar' i]",

        "input[placeholder*='job title' i]",
        "input[placeholder*='job' i]",
        "input[placeholder*='keyword' i]",
        "input[placeholder*='vaga' i]",
        "input[placeholder*='emprego' i]",
    )

    # =========================================================
    # JOB LINKS
    # =========================================================

    JOB_LINK_SELECTORS = (
        "a[href*='/job/']",
        "a[href*='/jobs/']",
        "a[href*='/vaga/']",
        "a[href*='/vagas/']",
        "a[href*='requisition']",
        "a[href*='opportunity']",

        "a[href*='jobId' i]",
        "a[href*='job-id' i]",
        "a[href*='jobid' i]",
        "a[href*='jobPosting' i]",
        "a[href*='jobposting' i]",

        "a[href*='vacancy' i]",
        "a[href*='vacancies' i]",
    )

    # =========================================================
    # JOB RESULT CONTAINERS
    # =========================================================

    JOB_RESULT_SELECTORS = (
        "[class*='job-card' i]",
        "[class*='job_card' i]",
        "[class*='jobcard' i]",

        "[class*='job-result' i]",
        "[class*='job_result' i]",
        "[class*='jobresult' i]",

        "[class*='job-listing' i]",
        "[class*='job_listing' i]",
        "[class*='joblisting' i]",

        "[class*='vacancy' i]",
        "[class*='vacancies' i]",

        "[class*='vaga' i]",
        "[class*='vagas' i]",

        "[data-job-id]",
        "[data-jobid]",
        "[data-job]",
        "[data-requisition-id]",
        "[data-requisitionid]",
    )

    # =========================================================
    # COOKIE DIALOGS
    # =========================================================

    COOKIE_DIALOG_SELECTORS = (
        "#CybotCookiebotDialog",
        "#onetrust-banner-sdk",
        "#onetrust-consent-sdk",

        "[id*='cookie' i][role='dialog']",
        "[class*='cookie' i][role='dialog']",

        "[id*='consent' i][role='dialog']",
        "[class*='consent' i][role='dialog']",

        "[id*='cookie-banner' i]",
        "[class*='cookie-banner' i]",
        "[id*='cookiebanner' i]",
        "[class*='cookiebanner' i]",

        "[id*='consent-banner' i]",
        "[class*='consent-banner' i]",
    )

    COOKIE_BUTTON_SELECTORS = (
        "#CybotCookiebotDialogBodyButtonDecline",
        "button:has-text('Use necessary cookies only')",

        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "button:has-text('Allow all cookies')",
        "button:has-text('Allow all')",

        "#onetrust-reject-all-handler",
        "#onetrust-accept-btn-handler",

        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('Agree')",
        "button:has-text('Reject all')",
        "button:has-text('Reject')",
        "button:has-text('Decline')",

        "button:has-text('Aceitar todos')",
        "button:has-text('Aceitar')",
        "button:has-text('Concordo')",
        "button:has-text('Rejeitar todos')",
        "button:has-text('Rejeitar')",
        "button:has-text('Recusar')",
        "button:has-text('Somente necessários')",
        "button:has-text('Apenas necessários')",
    )

    # =========================================================
    # MAIN ANALYZER
    # =========================================================

    async def analyze(
        self,
        page: Page,
        source_url: str,
    ) -> CareerScanResult:

        await self._wait_for_page(page)

        # -----------------------------------------------------
        # STEP 0 - Cookies
        # -----------------------------------------------------

        cookie_found = await self._handle_cookie_consent(
            page
        )

        if cookie_found:
            print(
                "    Cookie dialog was detected."
            )

        print(
            "    Analyzing career page..."
        )

        # -----------------------------------------------------
        # STEP 1 - Initial jobs
        # -----------------------------------------------------

        initial_jobs = await self._collect_jobs(
            page=page,
            source_url=source_url,
        )

        print(
            "    Job links detected on initial page: "
            f"{len(initial_jobs)}"
        )

        initial_has_results = (
            await self._has_job_results(page)
        )

        print(
            "    Job results detected on initial page: "
            f"{'YES' if initial_has_results else 'NO'}"
        )

        # -----------------------------------------------------
        # QA jobs already visible
        # -----------------------------------------------------

        initial_qa_jobs = self._filter_qa_jobs(
            initial_jobs
        )

        if initial_qa_jobs:

            print(
                "    QA jobs found on initial page: "
                f"{len(initial_qa_jobs)}"
            )

            self._print_qa_jobs(
                initial_qa_jobs
            )

            return CareerScanResult(
                success=True,
                page_good=True,
                jobs=initial_qa_jobs,
                message=(
                    "QA jobs found on initial page"
                ),
            )

        # -----------------------------------------------------
        # STEP 2 - Find search input
        # -----------------------------------------------------

        print(
            "    No QA job found on initial page."
        )

        print(
            "    Looking for search input..."
        )

        search_input = (
            await self._find_search_input(page)
        )

        # -----------------------------------------------------
        # No search field
        # -----------------------------------------------------

        if not search_input:

            print(
                "    Search input not found."
            )

            if initial_jobs:

                return CareerScanResult(
                    success=True,
                    page_good=True,
                    jobs=[],
                    message=(
                        "Career page has jobs, "
                        "but no QA job or search input found"
                    ),
                )

            if initial_has_results:

                return CareerScanResult(
                    success=True,
                    page_good=True,
                    jobs=[],
                    message=(
                        "Career page appears to have job "
                        "results, but job links could not "
                        "be extracted"
                    ),
                )

            return CareerScanResult(
                success=True,
                page_good=False,
                jobs=[],
                message=(
                    "No jobs, job results, or search input "
                    "detected"
                ),
            )

        # -----------------------------------------------------
        # STEP 3 - Search multiple terms
        # -----------------------------------------------------

        print(
            "    Search input found."
        )

        print(
            "    Search terms: "
            f"{', '.join(self.SEARCH_TERMS)}"
        )

        searched_jobs = (
            await self._search_multiple_terms(
                page=page,
                search_input=search_input,
                source_url=source_url,
            )
        )

        print(
            "    Unique jobs detected after all searches: "
            f"{len(searched_jobs)}"
        )

        # -----------------------------------------------------
        # STEP 4 - QA relevance filtering
        # -----------------------------------------------------

        qa_jobs = self._filter_qa_jobs(
            searched_jobs
        )

        # -----------------------------------------------------
        # QA jobs found
        # -----------------------------------------------------

        if qa_jobs:

            print(
                "    QA jobs found after multi-term search: "
                f"{len(qa_jobs)}"
            )

            self._print_qa_jobs(
                qa_jobs
            )

            return CareerScanResult(
                success=True,
                page_good=True,
                jobs=qa_jobs,
                message=(
                    "QA jobs found after multi-term search"
                ),
            )

        # -----------------------------------------------------
        # No QA jobs
        # -----------------------------------------------------

        searched_has_results = (
            await self._has_job_results(page)
        )

        if searched_jobs:

            message = (
                "Jobs found after multi-term search, "
                "but no QA jobs matched"
            )

        elif searched_has_results:

            message = (
                "Search returned job results, "
                "but job links could not be extracted"
            )

        else:

            message = (
                "No QA jobs found after multi-term search"
            )

        print(
            f"    {message}"
        )

        return CareerScanResult(
            success=True,
            page_good=True,
            jobs=[],
            message=message,
        )

    # =========================================================
    # PERSIST QA RESULTS
    # =========================================================
    #
    # This method is intentionally separate from analyze().
    #
    # analyze() only analyzes.
    #
    # This method persists ONLY QA jobs.
    # =========================================================

    @staticmethod
    def save_qa_results(
        source_id: int,
        result: CareerScanResult,
    ) -> int:

        qa_jobs = result.jobs or []

        active_urls = []

        inserted = 0

        for job in qa_jobs:

            job_url = (
                CareerAnalyzer._normalize_job_url(
                    job.url
                )
            )

            active_urls.append(
                job_url
            )

            insert_career_job(
                career_source_id=source_id,
                title=job.title,
                company=None,
                location=None,
                url=job_url,
                raw_data=job.raw_data,
            )

            inserted += 1

        # -----------------------------------------------------
        # Important:
        #
        # career_jobs contains ONLY QA jobs.
        #
        # Therefore deactivate_missing_jobs() also operates
        # only against the QA jobs stored for this source.
        # -----------------------------------------------------

        deactivate_missing_jobs(
            career_source_id=source_id,
            active_urls=active_urls,
        )

        # -----------------------------------------------------
        # Update career source statistics.
        # -----------------------------------------------------

        update_career_source_status(
            source_id=source_id,
            discovered_jobs=inserted,
        )

        mark_source_checked(
            source_id=source_id,
            success=result.success,
            error=(
                None
                if result.success
                else result.message
            ),
        )

        return inserted

    # =========================================================
    # PRINT QA JOBS
    # =========================================================

    @staticmethod
    def _print_qa_jobs(
        jobs: list[CareerJob],
    ) -> None:

        for job in jobs:

            print(
                f"      ✓ {job.title}"
            )

            print(
                f"        {job.url}"
            )

    # =========================================================
    # WAIT FOR PAGE
    # =========================================================

    async def _wait_for_page(
        self,
        page: Page,
    ) -> None:

        try:

            await page.wait_for_load_state(
                "domcontentloaded",
                timeout=30_000,
            )

        except PlaywrightTimeoutError:
            pass

        try:

            await page.locator("body").wait_for(
                state="visible",
                timeout=15_000,
            )

        except PlaywrightTimeoutError:
            pass

        await page.wait_for_timeout(
            2_000
        )

    # =========================================================
    # COOKIE HANDLING
    # =========================================================

    async def _handle_cookie_consent(
        self,
        page: Page,
    ) -> bool:

        found_dialog = False

        for dialog_selector in (
            self.COOKIE_DIALOG_SELECTORS
        ):

            try:

                dialog = page.locator(
                    dialog_selector
                ).first

                if not await dialog.is_visible(
                    timeout=1_000
                ):
                    continue

                found_dialog = True

                print(
                    "    Cookie dialog detected: "
                    f"{dialog_selector}"
                )

                for button_selector in (
                    self.COOKIE_BUTTON_SELECTORS
                ):

                    try:

                        button = page.locator(
                            button_selector
                        ).first

                        if not await button.is_visible(
                            timeout=500
                        ):
                            continue

                        print(
                            "    Cookie button found: "
                            f"{button_selector}"
                        )

                        try:

                            await button.click(
                                timeout=3_000
                            )

                        except Exception:

                            try:

                                await button.click(
                                    force=True,
                                    timeout=3_000,
                                )

                            except Exception:
                                continue

                        await page.wait_for_timeout(
                            700
                        )

                        try:

                            still_visible = (
                                await dialog.is_visible(
                                    timeout=1_000
                                )
                            )

                        except Exception:

                            still_visible = False

                        if not still_visible:

                            print(
                                "    Cookie dialog dismissed."
                            )

                            return True

                    except Exception:
                        continue

                print(
                    "    Cookie dialog found, "
                    "but no known dismissal button worked."
                )

                print(
                    "    Continuing anyway."
                )

                return True

            except Exception:
                continue

        return found_dialog

    # =========================================================
    # COLLECT JOBS
    # =========================================================

    async def _collect_jobs(
        self,
        page: Page,
        source_url: str,
    ) -> list[CareerJob]:

        links = page.locator(
            ",".join(
                self.JOB_LINK_SELECTORS
            )
        )

        count = await links.count()

        jobs: list[CareerJob] = []

        seen_urls: set[str] = set()

        for index in range(count):

            link = links.nth(index)

            try:

                if not await link.is_visible():
                    continue

                title = self._normalize(
                    await link.inner_text()
                )

                if not title or len(title) < 3:
                    continue

                href = await link.get_attribute(
                    "href"
                )

                if not href:
                    continue

                job_url = urljoin(
                    source_url,
                    href,
                )

                job_url = self._normalize_job_url(
                    job_url
                )

                if job_url in seen_urls:
                    continue

                if not self._looks_like_job(
                    title,
                    job_url,
                ):
                    continue

                seen_urls.add(
                    job_url
                )

                jobs.append(
                    CareerJob(
                        title=title,
                        url=job_url,
                        raw_data={
                            "title": title,
                            "href": href,
                        },
                    )
                )

            except Exception:
                continue

        return jobs

    # =========================================================
    # MULTI-TERM SEARCH
    # =========================================================

    async def _search_multiple_terms(
        self,
        page: Page,
        search_input,
        source_url: str,
    ) -> list[CareerJob]:

        all_jobs: dict[str, CareerJob] = {}

        for term_index, term in enumerate(
            self.SEARCH_TERMS,
            start=1,
        ):

            print("")

            print(
                f"    [Search {term_index}/"
                f"{len(self.SEARCH_TERMS)}] "
                f"Searching: {term}"
            )

            # -------------------------------------------------
            # Re-find input because some sites re-render it.
            # -------------------------------------------------

            current_input = (
                await self._find_search_input(page)
            )

            if not current_input:

                print(
                    "      Search input no longer "
                    "available."
                )

                break

            # -------------------------------------------------
            # Execute search
            # -------------------------------------------------

            search_success = (
                await self._perform_search(
                    page=page,
                    search_input=current_input,
                    term=term,
                )
            )

            if not search_success:

                print(
                    f"      Search failed for: {term}"
                )

                continue

            # -------------------------------------------------
            # Cookie dialog can appear again.
            # -------------------------------------------------

            await self._handle_cookie_consent(
                page
            )

            # -------------------------------------------------
            # Collect jobs
            # -------------------------------------------------

            jobs = await self._collect_jobs(
                page=page,
                source_url=source_url,
            )

            print(
                f"      Jobs found for '{term}': "
                f"{len(jobs)}"
            )

            # -------------------------------------------------
            # Deduplicate
            # -------------------------------------------------

            new_count = 0
            duplicate_count = 0

            for job in jobs:

                key = self._job_key(
                    job
                )

                if key in all_jobs:

                    duplicate_count += 1

                    self._append_search_term(
                        all_jobs[key],
                        term,
                    )

                    continue

                self._append_search_term(
                    job,
                    term,
                )

                all_jobs[key] = job

                new_count += 1

            print(
                f"      New unique jobs: "
                f"{new_count}"
            )

            if duplicate_count:

                print(
                    f"      Duplicates ignored: "
                    f"{duplicate_count}"
                )

            # -------------------------------------------------
            # QA matches for this search
            # -------------------------------------------------

            term_qa_jobs = (
                self._filter_qa_jobs(jobs)
            )

            if term_qa_jobs:

                print(
                    f"      QA matches for '{term}': "
                    f"{len(term_qa_jobs)}"
                )

                for job in term_qa_jobs:

                    print(
                        f"        ✓ {job.title}"
                    )

            else:

                print(
                    f"      No QA title matches "
                    f"for '{term}'"
                )

        return list(
            all_jobs.values()
        )

    # =========================================================
    # PERFORM SEARCH
    # =========================================================

    async def _perform_search(
        self,
        page: Page,
        search_input,
        term: str,
    ) -> bool:

        try:

            print(
                "      Search input:"
            )

            print(
                f"        name="
                f"{await search_input.get_attribute('name')}"
            )

            print(
                f"        id="
                f"{await search_input.get_attribute('id')}"
            )

            print(
                f"        placeholder="
                f"{await search_input.get_attribute('placeholder')}"
            )

            await search_input.fill(
                ""
            )

            await search_input.fill(
                term
            )

            await search_input.press(
                "Enter"
            )

            try:

                await page.wait_for_load_state(
                    "networkidle",
                    timeout=10_000,
                )

            except PlaywrightTimeoutError:
                pass

            await page.wait_for_timeout(
                2_000
            )

            print(
                f"      URL: {page.url}"
            )

            return True

        except Exception as error:

            print(
                f"      Search error: {error}"
            )

            return False

    # =========================================================
    # FILTER QA JOBS
    # =========================================================

    def _filter_qa_jobs(
        self,
        jobs: list[CareerJob],
    ) -> list[CareerJob]:

        result = []

        seen: set[str] = set()

        for job in jobs:

            if not self.QA_PATTERN.search(
                job.title
            ):
                continue

            key = self._job_key(
                job
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            result.append(
                job
            )

        return result

    # =========================================================
    # JOB DEDUPLICATION KEY
    # =========================================================

    def _job_key(
        self,
        job: CareerJob,
    ) -> str:

        return self._normalize_job_url(
            job.url
        ).casefold()

    # =========================================================
    # NORMALIZE JOB URL
    # =========================================================

    @staticmethod
    def _normalize_job_url(
        url: str,
    ) -> str:

        try:

            parsed = urlparse(
                url
            )

            normalized = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path.rstrip("/"),
                    "",
                    "",
                    "",
                )
            )

            return normalized

        except Exception:

            return url.split(
                "#",
                1,
            )[0].split(
                "?",
                1,
            )[0].rstrip("/")

    # =========================================================
    # REMEMBER SEARCH TERM
    # =========================================================

    @staticmethod
    def _append_search_term(
        job: CareerJob,
        term: str,
    ) -> None:

        raw_data = job.raw_data

        if not isinstance(
            raw_data,
            dict,
        ):
            return

        terms = raw_data.setdefault(
            "search_terms",
            [],
        )

        if term not in terms:

            terms.append(
                term
            )

    # =========================================================
    # DETECT JOB RESULTS
    # =========================================================

    async def _has_job_results(
        self,
        page: Page,
    ) -> bool:

        body_text = ""

        try:

            body_text = self._normalize(
                await page.locator(
                    "body"
                ).inner_text()
            ).casefold()

        except Exception:
            pass

        if body_text:

            no_result_patterns = (
                "no jobs found",
                "no results found",
                "no results",
                "no matching jobs",
                "nenhuma vaga encontrada",
                "nenhuma vaga foi encontrada",
                "nenhum resultado",
                "não encontramos vagas",
                "nao encontramos vagas",
                "nenhuma oportunidade encontrada",
                "nenhuma oportunidade foi encontrada",
            )

            for pattern in no_result_patterns:

                if pattern in body_text:

                    print(
                        "    Explicit no-results message "
                        f"detected: '{pattern}'"
                    )

                    return False

        # -----------------------------------------------------
        # Known result containers
        # -----------------------------------------------------

        for selector in (
            self.JOB_RESULT_SELECTORS
        ):

            try:

                locator = page.locator(
                    selector
                )

                count = await locator.count()

                if count == 0:
                    continue

                visible_count = 0

                for index in range(
                    min(count, 30)
                ):

                    try:

                        element = locator.nth(
                            index
                        )

                        if await element.is_visible():

                            visible_count += 1

                    except Exception:
                        continue

                if visible_count > 0:

                    print(
                        "    Job result container "
                        f"detected: {selector} "
                        f"({visible_count} visible)"
                    )

                    return True

            except Exception:
                continue

        # -----------------------------------------------------
        # Generic list items
        # -----------------------------------------------------

        try:

            list_items = page.locator(
                "li"
            )

            count = await list_items.count()

            checked = 0

            for index in range(
                min(count, 100)
            ):

                if checked >= 30:
                    break

                try:

                    element = list_items.nth(
                        index
                    )

                    if not await element.is_visible():
                        continue

                    text = self._normalize(
                        await element.inner_text()
                    )

                    if len(text) < 10:
                        continue

                    checked += 1

                    if self.QA_PATTERN.search(
                        text
                    ):

                        print(
                            "    Job-like list item "
                            "detected through QA text."
                        )

                        return True

                except Exception:
                    continue

        except Exception:
            pass

        return False

    # =========================================================
    # FIND SEARCH INPUT
    # =========================================================

    async def _find_search_input(
        self,
        page: Page,
    ):

        for selector in (
            self.SEARCH_SELECTORS
        ):

            locator = page.locator(
                selector
            )

            try:

                count = await locator.count()

                for index in range(count):

                    element = locator.nth(
                        index
                    )

                    if not await element.is_visible():
                        continue

                    try:

                        if not await element.is_enabled():
                            continue

                    except Exception:
                        pass

                    if await self._is_location_input(
                        element
                    ):
                        continue

                    print(
                        "    Selected search input: "
                        f"{selector}"
                    )

                    return element

            except Exception:
                continue

        # -----------------------------------------------------
        # Fallback scoring
        # -----------------------------------------------------

        inputs = page.locator(
            "input[type='text'], input:not([type])"
        )

        count = await inputs.count()

        candidates = []

        for index in range(count):

            element = inputs.nth(
                index
            )

            try:

                if not await element.is_visible():
                    continue

                if not await element.is_enabled():
                    continue

                if await self._is_location_input(
                    element
                ):
                    continue

                score = (
                    await self._search_input_score(
                        element
                    )
                )

                if score > 0:

                    candidates.append(
                        (
                            score,
                            element,
                        )
                    )

            except Exception:
                continue

        if candidates:

            candidates.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            selected = candidates[0][1]

            print(
                "    Selected search input "
                "using fallback scoring"
            )

            return selected

        return None

    # =========================================================
    # DETERMINE LOCATION INPUT
    # =========================================================

    async def _is_location_input(
        self,
        element,
    ) -> bool:

        attributes = (
            await element.get_attribute("name"),
            await element.get_attribute("id"),
            await element.get_attribute("placeholder"),
            await element.get_attribute("aria-label"),
        )

        text = " ".join(
            value or ""
            for value in attributes
        ).casefold()

        location_terms = (
            "location",
            "localização",
            "localizacao",
            "cidade",
            "city",
            "where",
            "onde",
            "postcode",
            "postal",
            "zip",
        )

        return any(
            term in text
            for term in location_terms
        )

    # =========================================================
    # SEARCH INPUT SCORE
    # =========================================================

    async def _search_input_score(
        self,
        element,
    ) -> int:

        attributes = (
            await element.get_attribute("name"),
            await element.get_attribute("id"),
            await element.get_attribute("placeholder"),
            await element.get_attribute("aria-label"),
        )

        text = " ".join(
            value or ""
            for value in attributes
        ).casefold()

        score = 0

        if text.strip() == "q":
            score += 100

        if "job" in text:
            score += 50

        if "keyword" in text:
            score += 40

        if "search" in text:
            score += 30

        if "buscar" in text:
            score += 30

        if "pesquis" in text:
            score += 30

        if "vaga" in text:
            score += 40

        if "emprego" in text:
            score += 40

        if "oportunidade" in text:
            score += 30

        if any(
            term in text
            for term in (
                "location",
                "localização",
                "localizacao",
                "cidade",
                "city",
                "where",
                "onde",
            )
        ):

            score -= 100

        return score

    # =========================================================
    # DETERMINE WHETHER LINK LOOKS LIKE A JOB
    # =========================================================

    @classmethod
    def _looks_like_job(
        cls,
        title: str,
        url: str,
    ) -> bool:

        url_value = url.casefold()

        title_value = title.casefold()

        ignored_titles = {
            "jobs",
            "job search",
            "careers",
            "career",
            "vagas",
            "todas as vagas",
            "all jobs",
            "search jobs",
            "buscar vagas",
            "pesquisar vagas",
        }

        if title_value in ignored_titles:
            return False

        job_url_indicators = (
            "/job",
            "/jobs",
            "/vaga",
            "/vagas",
            "job=",
            "jobid",
            "job-id",
            "jobposting",
            "requisition",
            "opportunity",
            "vacancy",
            "vacancies",
        )

        if any(
            indicator in url_value
            for indicator in job_url_indicators
        ):
            return True

        if cls.QA_PATTERN.search(
            title
        ):
            return True

        return False

    # =========================================================
    # NORMALIZE TEXT
    # =========================================================

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:

        return re.sub(
            r"\s+",
            " ",
            value or "",
        ).strip()