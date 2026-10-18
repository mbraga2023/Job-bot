# agents/analyzers/career.py

import json
import re
from urllib.parse import (
    parse_qsl,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

import ollama

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from core.career_result import (
    CareerJob,
    CareerScanResult,
)

from core.keywords import QA_SEARCH_TERMS

from database.career_jobs import (
    insert_career_job,
    deactivate_missing_jobs,
)

from database.career_sources import (
    mark_source_checked,
    update_career_source_status,
)


class CareerAnalyzer:
    """
    Discovers QA job openings on company career pages.

    Strategy:
    1. Collect jobs using deterministic Playwright selectors.
    2. If no QA jobs are found, locate a search field.
    3. Use deterministic field detection first.
    4. Use local Ollama/Qwen3 only if deterministic detection fails.
    5. Search using configured QA keywords.
    """

    QA_PATTERN = re.compile(
        r"\b("
        r"qa|"
        r"quality assurance|"
        r"quality engineer|"
        r"quality analyst|"
        r"software tester|"
        r"software testing|"
        r"test engineer|"
        r"test analyst|"
        r"automation engineer|"
        r"automated testing|"
        r"analista de testes|"
        r"analista de qualidade|"
        r"engenheiro de testes|"
        r"engenheira de testes|"
        r"testes de software|"
        r"tester|"
        r"qa analyst|"
        r"qa engineer|"
        r"qe\b"
        r")\b",
        re.IGNORECASE,
    )

    SEARCH_SELECTORS = [
        'input[type="search"]',
        'input[placeholder*="search" i]',
        'input[placeholder*="buscar" i]',
        'input[placeholder*="pesquisar" i]',
        'input[aria-label*="search" i]',
        'input[aria-label*="buscar" i]',
        'input[name*="search" i]',
        'input[id*="search" i]',
        'input[name*="query" i]',
        'input[id*="query" i]',
        'input[name*="keyword" i]',
        'input[id*="keyword" i]',
        'input[name*="term" i]',
        'input[id*="term" i]',
        '[role="search"] input',
        'form[role="search"] input',
    ]

    JOB_LINK_SELECTORS = [
        'a[href*="/job/" i]',
        'a[href*="/jobs/" i]',
        'a[href*="/career/" i]',
        'a[href*="/careers/" i]',
        'a[href*="/position/" i]',
        'a[href*="/positions/" i]',
        'a[href*="/vacancy/" i]',
        'a[href*="/vacancies/" i]',
        'a[href*="/opening/" i]',
        'a[href*="/openings/" i]',
        'a[href*="/requisition/" i]',
        'a[href*="/requisitions/" i]',
        'a[href*="/apply/" i]',
        'a[href*="gh_jid=" i]',
        'a[href*="jobid=" i]',
        'a[href*="jobId=" i]',
        'a[href*="job_id=" i]',
        'a[href*="lever.co/" i]',
        'a[href*="greenhouse.io/" i]',
        'a[href*="workdayjobs.com/" i]',
        'a[href*="ashbyhq.com/" i]',
        'a[href*="smartrecruiters.com/" i]',
        'a[href*="gupy.io/" i]',
    ]

    JOB_RESULT_SELECTORS = [
        "[data-job-id]",
        '[data-testid*="job" i]',
        '[class*="job-listing" i]',
        '[class*="job-card" i]',
        '[class*="job-result" i]',
        '[class*="job-item" i]',
        '[class*="opening" i]',
        '[class*="position-card" i]',
        '[class*="vacancy" i]',
        'li[class*="job" i]',
    ]

    COOKIE_SELECTORS = [
        'button:has-text("Accept all")',
        'button:has-text("Accept cookies")',
        'button:has-text("Accept")',
        'button:has-text("I agree")',
        'button:has-text("Agree")',
        'button:has-text("Aceitar todos")',
        'button:has-text("Aceitar cookies")',
        'button:has-text("Aceitar")',
        'button:has-text("Concordo")',
        'button:has-text("Entendi")',
    ]

    NO_RESULTS_PATTERNS = [
        "no jobs found",
        "no results found",
        "no matching jobs",
        "no open positions",
        "no positions found",
        "no vacancies found",
        "no openings found",
        "no jobs match",
        "0 jobs",
        "nenhuma vaga encontrada",
        "nenhum resultado encontrado",
        "nenhuma vaga disponível",
        "nenhuma vaga disponivel",
        "não encontramos vagas",
        "nao encontramos vagas",
        "não foram encontradas vagas",
        "nao foram encontradas vagas",
        "nenhum resultado",
    ]

    def __init__(
        self,
        source=None,
        ollama_model="qwen3:4b",
        ai_enabled=True,
        ai_confidence_threshold=0.65,
    ):
        self.source = source
        self.ollama_model = ollama_model
        self.ai_enabled = ai_enabled
        self.ai_confidence_threshold = ai_confidence_threshold

    async def analyze(self, page: Page, source_url: str) -> CareerScanResult:
        """
        Analyze a career page and return discovered QA jobs.

        The existing deterministic discovery remains the primary strategy.
        Local AI is only used as a fallback when search-field discovery fails.
        """
        try:
            if page.is_closed():
                return CareerScanResult(
                    success=True,
                    page_good=True,
                    jobs=[],
                    message="No searchable field was found.",
                )

            try:
                await page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=15000,
                )
            except PlaywrightTimeoutError:
                pass

            await self._handle_cookies(page)

            initial_jobs = await self._collect_jobs(page, source_url)
            initial_qa_jobs = self._filter_qa_jobs(initial_jobs)

            if initial_qa_jobs:
                return CareerScanResult(
                    success=True,
                    jobs=initial_qa_jobs,
                    page_good=False,
                    message=(
                        f"Found {len(initial_qa_jobs)} QA job(s) "
                        "without using the search field."
                    ),
                )

            if await self._has_job_results(page):
                print(
                    "    Job results were detected, but no QA jobs "
                    "matched the current title keywords."
                )

            search_input = await self._find_search_input(page)

            if search_input is None:
                return CareerScanResult(
                    success=True,
                    page_good=True,
                    jobs=[],
                    message=(
                        "No searchable field was found. " "No QA jobs were identified."
                    ),
                )

            discovered_jobs = await self._search_multiple_terms(
                page=page,
                source_url=source_url,
            )

            qa_jobs = self._filter_qa_jobs(discovered_jobs)

            return CareerScanResult(
                success=True,
                page_good=True,
                jobs=qa_jobs,
                message=(
                    f"Found {len(qa_jobs)} QA job(s) after "
                    f"searching the career page."
                ),
            )

        except Exception as exc:
            return CareerScanResult(
                success=False,
                page_good=True,
                jobs=[],
                message=f"Career page analysis failed: {exc}",
            )

    async def save_qa_results(
        self,
        source_id,
        result: CareerScanResult,
    ):
        """
        Save discovered QA jobs.

        Missing jobs are deactivated only when this scan actually returned
        jobs, avoiding accidental deactivation after an empty scan.
        """
        if not result.success:
            print(f"    Scan failed; jobs were not deactivated: {result.message}")
            return

        saved_count = 0

        for job in result.jobs:
            try:
                insert_career_job(source_id, job)
                saved_count += 1
            except Exception as exc:
                print(
                    f"    Could not save job "
                    f"{getattr(job, 'title', 'Unknown')}: {exc}"
                )

        if result.jobs:
            try:
                deactivate_missing_jobs(
                    source_id,
                    [job.url for job in result.jobs],
                )
            except Exception as exc:
                print(f"    Could not deactivate missing jobs: {exc}")

        try:
            mark_source_checked(source_id)
        except Exception as exc:
            print(f"    Could not update last-checked time: {exc}")

        try:
            update_career_source_status(
                source_id,
                success=True,
                message=result.message,
            )
        except TypeError:
            # Some implementations may use a different function signature.
            try:
                update_career_source_status(source_id, True)
            except Exception as exc:
                print(f"    Could not update source status: {exc}")
        except Exception as exc:
            print(f"    Could not update source status: {exc}")

        print(f"    Saved {saved_count} QA job(s).")

    async def _handle_cookies(self, page: Page):
        """Try common cookie-consent buttons without failing the scan."""
        for selector in self.COOKIE_SELECTORS:
            try:
                button = page.locator(selector).first

                if await button.count() and await button.is_visible():
                    await button.click(timeout=2000)
                    await page.wait_for_timeout(500)
                    print("    Cookie consent handled.")
                    return

            except Exception:
                continue


    async def _collect_jobs(
        self,
        page: Page,
        source_url: str,
        search_term=None,
    ):
        """Collect job-like links from the main page and all frames."""

        jobs_by_url = {}

        for frame in page.frames:
            base_url = frame.url or source_url

            for selector in self.JOB_LINK_SELECTORS:
                try:
                    links = frame.locator(selector)
                    count = min(await links.count(), 300)

                    for index in range(count):
                        link = links.nth(index)

                        try:
                            if not await link.is_visible():
                                continue

                            href = await link.get_attribute("href")
                            title = (await link.inner_text(timeout=1500)).strip()

                            if not href:
                                continue

                            absolute_url = urljoin(base_url, href)
                            absolute_url = self._normalize_job_url(absolute_url)

                            if not self._looks_like_job(
                                title,
                                absolute_url,
                            ):
                                continue

                            if not title:
                                title = await self._title_from_url(absolute_url)

                            if not title:
                                continue

                            key = self._normalize_url_for_dedup(absolute_url)

                            if key not in jobs_by_url:
                                jobs_by_url[key] = CareerJob(
                                    title=title,
                                    url=absolute_url,
                                    raw_data=(
                                        {"search_term": search_term}
                                        if search_term
                                        else None
                                    ),
                                )

                        except Exception:
                            continue

                except Exception:
                    continue

        print(
            f"    Collected {len(jobs_by_url)} unique job link(s) "
            f"across {len(page.frames)} frame(s)."
        )

        return list(jobs_by_url.values())

    async def _title_from_url(self, url: str) -> str:
        """Create a readable fallback title from a URL slug."""
        parsed = urlparse(url)
        slug = parsed.path.rstrip("/").split("/")[-1]

        if not slug:
            return ""

        slug = re.sub(r"[-_]+", " ", slug)
        slug = re.sub(r"\.(html?|aspx?)$", "", slug, flags=re.IGNORECASE)
        slug = re.sub(r"\b[0-9a-f]{8,}\b", "", slug, flags=re.IGNORECASE)

        return " ".join(slug.split()).strip().title()

    async def _search_multiple_terms(
        self,
        page: Page,
        source_url: str,
    ):
        """Search the career page using each configured QA keyword."""
        all_jobs = {}
        searched_terms = set()

        for term in QA_SEARCH_TERMS:
            term = str(term).strip()

            if not term or term.lower() in searched_terms:
                continue

            searched_terms.add(term.lower())

            search_input = await self._find_search_input(page)

            if search_input is None:
                print("    Search field is no longer available.")
                break

            try:
                await self._perform_search(page, search_input, term)

                found_jobs = await self._collect_jobs(
                    page=page,
                    source_url=source_url,
                    search_term=term,
                )

                for job in found_jobs:
                    key = self._normalize_url_for_dedup(job.url)

                    if key not in all_jobs:
                        all_jobs[key] = job

                print(f"    Search '{term}': " f"{len(found_jobs)} job link(s) found.")

            except Exception as exc:
                print(f"    Search '{term}' failed: {exc}")
                continue

        return list(all_jobs.values())

    async def _perform_search(
        self,
        page: Page,
        search_input,
        term: str,
    ):
        """
        Fill the search field and submit it.

        Enter is attempted first. If it does not produce a usable result,
        try a nearby submit button.
        """
        await search_input.fill(term, timeout=5000)
        await page.wait_for_timeout(300)

        try:
            await search_input.press("Enter", timeout=3000)
        except Exception:
            pass

        await self._wait_for_search_results(page)

        if await self._has_job_results(page):
            return

        # Some career sites require clicking a search button.
        button_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button[aria-label*="search" i]',
            'button[aria-label*="buscar" i]',
            'button:has-text("Search")',
            'button:has-text("Buscar")',
            'button:has-text("Pesquisar")',
        ]

        for selector in button_selectors:
            try:
                buttons = page.locator(selector)
                count = min(await buttons.count(), 10)

                for index in range(count):
                    button = buttons.nth(index)

                    if not await button.is_visible():
                        continue

                    await button.click(timeout=2000)
                    await self._wait_for_search_results(page)

                    if await self._has_job_results(page):
                        return

            except Exception:
                continue

    async def _wait_for_search_results(self, page: Page):
        """Wait for search navigation or asynchronous result updates."""
        try:
            await page.wait_for_load_state(
                "domcontentloaded",
                timeout=5000,
            )
        except PlaywrightTimeoutError:
            pass
        except Exception:
            pass

        try:
            await page.wait_for_load_state(
                "networkidle",
                timeout=4000,
            )
        except Exception:
            # Many career sites keep background requests open.
            pass

        await page.wait_for_timeout(1000)

    def _filter_qa_jobs(self, jobs):
        """Keep jobs whose titles match QA-related keywords."""
        filtered = []
        seen = set()

        for job in jobs:
            title = getattr(job, "title", "") or ""

            if not self.QA_PATTERN.search(title):
                continue

            key = self._normalize_url_for_dedup(getattr(job, "url", "") or "")

            if key in seen:
                continue

            seen.add(key)
            filtered.append(job)

        return filtered

    async def _has_job_results(self, page: Page) -> bool:
        """Check whether the current page appears to contain job results."""
        try:
            body_text = (await page.locator("body").inner_text(timeout=3000)).lower()
        except Exception:
            body_text = ""

        if any(pattern in body_text for pattern in self.NO_RESULTS_PATTERNS):
            return False

        for selector in self.JOB_RESULT_SELECTORS:
            try:
                elements = page.locator(selector)

                if await elements.count() > 0:
                    for index in range(min(await elements.count(), 10)):
                        element = elements.nth(index)

                        if await element.is_visible():
                            text = (await element.inner_text(timeout=1000)).strip()

                            if len(text) > 10:
                                return True

            except Exception:
                continue

        # Fall back to visible links that resemble job postings.
        try:
            links = page.locator("a[href]")
            count = min(await links.count(), 200)

            for index in range(count):
                link = links.nth(index)

                try:
                    if not await link.is_visible():
                        continue

                    href = await link.get_attribute("href") or ""
                    text = (await link.inner_text(timeout=1000)).strip()

                    if self._looks_like_job(text, href):
                        return True

                except Exception:
                    continue

        except Exception:
            pass

        return False


    async def _find_search_input(self, page: Page):
        """Find a keyword-search field in the main page or any iframe."""

        for frame in page.frames:
            print(f"    Checking search fields in frame: {frame.url}")

            # First: known search selectors.
            for selector in self.SEARCH_SELECTORS:
                try:
                    elements = frame.locator(selector)
                    count = min(await elements.count(), 10)

                    for index in range(count):
                        element = elements.nth(index)

                        if (
                            await element.is_visible()
                            and await element.is_enabled()
                            and not await self._is_location_input(element)
                        ):
                            print(f"    Search field found: {selector}")
                            return element

                except Exception:
                    continue

            # Second: score visible form fields.
            try:
                elements = frame.locator('input, textarea, [role="combobox"]')
                count = min(await elements.count(), 60)

                best_element = None
                best_score = 0

                for index in range(count):
                    element = elements.nth(index)

                    try:
                        if not await element.is_visible():
                            continue

                        if not await element.is_enabled():
                            continue

                        if await self._is_location_input(element):
                            continue

                        details = await self._get_input_details(element)
                        score = self._search_input_score(details)

                        if score > best_score:
                            best_score = score
                            best_element = element

                    except Exception:
                        continue

                if best_element is not None and best_score >= 2:
                    print(f"    Search field found by scoring " f"(score={best_score}).")
                    return best_element

            except Exception as exc:
                print(f"    Could not inspect frame fields: {exc}")

        # Third: ask local Qwen to choose a field in each frame.
        if self.ai_enabled:
            for frame in page.frames:
                print(f"    Trying local AI in frame: {frame.url}")

                try:
                    element = await self._find_search_input_with_ai(frame)

                    if element is not None:
                        return element

                except Exception as exc:
                    print(f"    AI frame inspection failed: {exc}")

        print("    No search field found in any frame.")
        return None

    async def _find_search_input_with_ai(self, page: Page):
        """
        Ask local Qwen3 to choose among visible form fields.

        The model only selects a candidate index. It does not receive
        filesystem access and cannot execute browser actions itself.
        """
        try:
            elements = page.locator('input, textarea, [role="combobox"]')
            count = min(await elements.count(), 40)

            candidates = []

            for index in range(count):
                element = elements.nth(index)

                try:
                    if not await element.is_visible():
                        continue

                    if not await element.is_enabled():
                        continue

                    if await self._is_location_input(element):
                        continue

                    details = await self._get_input_details(element)

                    # Exclude fields that are clearly unrelated to search.
                    field_type = (details.get("type") or "").lower()
                    combined = " ".join(
                        str(value) for value in details.values() if value is not None
                    ).lower()

                    if field_type in {
                        "password",
                        "email",
                        "checkbox",
                        "radio",
                        "hidden",
                        "submit",
                        "button",
                        "file",
                    }:
                        continue

                    if any(
                        word in combined
                        for word in [
                            "password",
                            "email address",
                            "e-mail",
                            "phone number",
                            "first name",
                            "last name",
                            "full name",
                            "your name",
                        ]
                    ):
                        continue

                    candidates.append(
                        {
                            "index": index,
                            "details": details,
                            "locator": element,
                        }
                    )

                except Exception:
                    continue

            if not candidates:
                print("    AI fallback: no eligible form fields found.")
                return None

            public_candidates = [
                {
                    "index": item["index"],
                    **item["details"],
                }
                for item in candidates
            ]

            prompt = f"""
You are identifying a job-search field on a company careers website.

Choose the candidate most likely used to search job vacancies by
keyword, job title, or skill.

Do not choose:
- Location, city, country, or distance fields
- Email, password, name, or phone fields
- Login, signup, or account fields
- Filters that are clearly unrelated to keyword search

Prefer fields whose placeholder, label, name, ID, or accessible label
indicates search, keyword, job title, position, role, or vacancy.

Return ONLY a JSON object in this format:
{{
  "index": 0,
  "confidence": 0.0,
  "reason": "brief explanation"
}}

If no suitable candidate exists, return index -1 and confidence 0.

Candidates:
{json.dumps(public_candidates, ensure_ascii=False)}
"""

            client = ollama.AsyncClient()

            response = await client.chat(
                model=self.ollama_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                think=False,
                format="json",
                options={
                    "temperature": 0,
                    "num_predict": 120,
                },
            )

            content = response.message.content

            if not content:
                print("    AI fallback returned an empty response.")
                return None

            try:
                decision = json.loads(content)
            except json.JSONDecodeError:
                print("    AI fallback returned invalid JSON.")
                return None

            selected_index = decision.get("index", -1)
            confidence = decision.get("confidence", 0)

            try:
                selected_index = int(selected_index)
                confidence = float(confidence)
            except (ValueError, TypeError):
                return None

            if selected_index < 0:
                print("    AI could not identify a search field.")
                return None

            if confidence < self.ai_confidence_threshold:
                print(
                    f"    AI confidence too low: {confidence:.2f}. "
                    "Ignoring its selection."
                )
                return None

            selected = next(
                (item for item in candidates if item["index"] == selected_index),
                None,
            )

            if selected is None:
                print("    AI selected an invalid candidate index.")
                return None

            # Recheck the selected element before returning it.
            locator = selected["locator"]

            if not await locator.is_visible():
                return None

            if not await locator.is_enabled():
                return None

            print(
                "    AI selected search field: "
                f"{selected['details']} "
                f"(confidence={confidence:.2f})"
            )

            return locator

        except Exception as exc:
            print(f"    Local AI fallback failed: {exc}")
            return None

    async def _get_input_details(self, element):
        """Extract visible, non-sensitive field metadata for classification."""
        try:
            details = await element.evaluate("""el => {
                    const labels = Array.from(el.labels || [])
                        .map(label => label.innerText || "")
                        .join(" ");

                    const labelledBy = el.getAttribute("aria-labelledby");
                    let labelledByText = "";

                    if (labelledBy) {
                        labelledByText = labelledBy
                            .split(/\\s+/)
                            .map(id => document.getElementById(id))
                            .filter(Boolean)
                            .map(node => node.innerText || "")
                            .join(" ");
                    }

                    return {
                        tag: el.tagName.toLowerCase(),
                        type: el.getAttribute("type") || "",
                        name: el.getAttribute("name") || "",
                        id: el.id || "",
                        placeholder: el.getAttribute("placeholder") || "",
                        aria_label: el.getAttribute("aria-label") || "",
                        aria_labelledby_text: labelledByText,
                        role: el.getAttribute("role") || "",
                        autocomplete: el.getAttribute("autocomplete") || "",
                        labels: labels
                    };
                }""")

            return details or {}

        except Exception:
            return {}

    async def _is_location_input(self, element) -> bool:
        """Exclude fields that appear to be location filters."""
        try:
            details = await self._get_input_details(element)
            combined = " ".join(
                str(value) for value in details.values() if value is not None
            ).lower()

            location_terms = [
                "location",
                "locations",
                "city",
                "country",
                "region",
                "state",
                "locality",
                "postal code",
                "zip code",
                "postcode",
                "distance",
                "near me",
                "localização",
                "localizacao",
                "cidade",
                "país",
                "pais",
                "estado",
                "região",
                "regiao",
                "distância",
                "distancia",
                "cep",
            ]

            return any(term in combined for term in location_terms)

        except Exception:
            return False

    def _search_input_score(self, details: dict) -> int:
        """Score a field using its accessible metadata."""
        combined = " ".join(
            str(value) for value in details.values() if value is not None
        ).lower()

        score = 0

        positive_terms = {
            "search": 5,
            "keyword": 5,
            "job title": 5,
            "position": 4,
            "vacancy": 4,
            "role": 3,
            "career": 3,
            "jobs": 3,
            "job": 3,
            "query": 3,
            "buscar": 5,
            "pesquisar": 5,
            "palavra-chave": 5,
            "palavra chave": 5,
            "cargo": 4,
            "vaga": 4,
            "oportunidade": 3,
        }

        negative_terms = [
            "location",
            "city",
            "country",
            "region",
            "postal code",
            "zip code",
            "email",
            "password",
            "first name",
            "last name",
            "phone",
            "localização",
            "localizacao",
            "cidade",
            "país",
            "pais",
            "cep",
        ]

        for term, weight in positive_terms.items():
            if term in combined:
                score += weight

        if any(term in combined for term in negative_terms):
            score -= 10

        field_type = (details.get("type") or "").lower()

        if field_type == "search":
            score += 5

        if field_type in {
            "password",
            "email",
            "checkbox",
            "radio",
            "hidden",
            "submit",
            "button",
            "file",
        }:
            score -= 20

        return score

    def _looks_like_job(self, title: str, url: str) -> bool:
        """Reject navigation links and URLs that do not resemble job postings."""
        title = (title or "").strip()
        url = (url or "").strip()

        if not url:
            return False

        parsed = urlparse(url)
        path = parsed.path.lower()
        query = parsed.query.lower()
        title_lower = title.lower()

        if parsed.scheme not in {"http", "https"}:
            return False

        if any(
            blocked in path
            for blocked in [
                "/login",
                "/signin",
                "/sign-in",
                "/signup",
                "/sign-up",
                "/privacy",
                "/terms",
                "/benefits",
                "/about",
                "/contact",
                "/events",
                "/blog",
                "/news",
            ]
        ):
            return False

        if any(
            word in title_lower
            for word in [
                "privacy policy",
                "cookie policy",
                "terms of use",
                "sign in",
                "log in",
                "create account",
                "view all jobs",
                "see all jobs",
                "ver todas as vagas",
                "carregar mais",
                "load more",
            ]
        ):
            return False

        job_url_patterns = [
            r"/jobs?(?:/|$)",
            r"/careers?(?:/|$)",
            r"/positions?(?:/|$)",
            r"/vacanc(?:y|ies)(?:/|$)",
            r"/openings?(?:/|$)",
            r"/requisitions?(?:/|$)",
            r"/apply(?:/|$)",
            r"gh_jid=",
            r"jobid=",
            r"job_id=",
            r"jobid%3d",
        ]

        url_text = f"{path}?{query}"

        if any(
            re.search(pattern, url_text, re.IGNORECASE) for pattern in job_url_patterns
        ):
            return True

        # On career pages, a descriptive link can still be a job listing
        # even when its URL does not contain a standard job keyword.
        if title and len(title) >= 8:
            if self.QA_PATTERN.search(title):
                return True

            generic_job_terms = [
                "engineer",
                "developer",
                "analyst",
                "manager",
                "specialist",
                "designer",
                "consultant",
                "tester",
                "quality",
                "engenheiro",
                "desenvolvedor",
                "analista",
                "especialista",
                "testador",
                "qualidade",
            ]

            if any(term in title_lower for term in generic_job_terms):
                return True

        return False

    def _normalize_job_url(self, url: str) -> str:
        """
        Normalize URLs while preserving query parameters that may identify jobs.

        Tracking parameters are removed, but job IDs and application parameters
        are retained.
        """
        try:
            parsed = urlparse(url)

            tracking_parameters = {
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_term",
                "utm_content",
                "gclid",
                "fbclid",
                "referrer",
                "source",
            }

            query_items = [
                (key, value)
                for key, value in parse_qsl(
                    parsed.query,
                    keep_blank_values=True,
                )
                if key.lower() not in tracking_parameters
            ]

            normalized_query = urlencode(query_items, doseq=True)

            return urlunparse(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    parsed.path.rstrip("/") or "/",
                    parsed.params,
                    normalized_query,
                    "",
                )
            )

        except Exception:
            return url

    def _normalize_url_for_dedup(self, url: str) -> str:
        """Normalize URLs for duplicate detection without changing stored URLs."""
        try:
            parsed = urlparse(url)

            return urlunparse(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    parsed.path.rstrip("/").lower() or "/",
                    parsed.params,
                    parsed.query,
                    "",
                )
            )

        except Exception:
            return url

    def is_gupy_url(self, url: str) -> bool:
        """Return True when a URL belongs to Gupy."""
        try:
            hostname = urlparse(url).netloc.lower()
            return "gupy.io" in hostname
        except Exception:
            return False
