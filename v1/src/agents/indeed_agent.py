from __future__ import annotations

import json
import re
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from config import TIMEOUT

INDEED_PROFILE_DIR = Path("storage/indeed_chrome_profile")
MANUAL_CHECK_TIMEOUT_SECONDS = 300


class _DescriptionTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


class _CapturedElement:
    def __init__(self, tag: str, attrs: dict[str, str | None]):
        self.tag = tag
        self.attrs = attrs
        self.content: list[str | _CapturedElement] = []

    def text(self) -> str:
        value = "".join(
            part if isinstance(part, str) else part.text()
            for part in self.content
        )
        return " ".join(value.split())


class _IndeedSnapshotParser(HTMLParser):
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.roots: list[_CapturedElement] = []
        self.root: _CapturedElement | None = None
        self.stack: list[_CapturedElement] = []
        self.source_url = ""

    def handle_comment(self, data: str):
        match = re.search(r"saved from url=\(\d+\)(https?://.+)", data)
        if match:
            self.source_url = match.group(1).strip()

    def handle_starttag(self, tag: str, attrs):
        attributes = dict(attrs)

        if self.root is None:
            classes = (attributes.get("class") or "").split()
            if (
                "cardOutline" not in classes
                and attributes.get("data-testid") != "viewjob-main-content"
            ):
                return

            node = _CapturedElement(tag, attributes)
            self.root = node
            self.stack = [node]
            return

        node = _CapturedElement(tag, attributes)
        self.stack[-1].content.append(node)
        if tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                if not self.stack and self.root:
                    self.roots.append(self.root)
                    self.root = None
                return

    def handle_data(self, data: str):
        if self.stack:
            self.stack[-1].content.append(data)


def _walk_elements(root: _CapturedElement):
    yield root
    for item in root.content:
        if isinstance(item, _CapturedElement):
            yield from _walk_elements(item)


def _parse_saved_html(html: str) -> dict:
    parser = _IndeedSnapshotParser()
    parser.feed(html)
    source_url = parser.source_url or "https://br.indeed.com/jobs"

    matching_jobs = []
    matched_ids = set()
    panes = []

    for root in parser.roots:
        if root.attrs.get("data-testid") == "viewjob-main-content":
            panes.append(root)
            continue

        elements = list(_walk_elements(root))
        title_link = next(
            (
                element
                for element in elements
                if element.tag == "a"
                and (
                    "jcs-JobTitle" in (element.attrs.get("class") or "").split()
                    or element.attrs.get("data-jk")
                )
            ),
            None,
        )
        if not title_link:
            continue

        title = title_link.text()
        card_text = root.text()
        if not _contains_target_keyword(f"{title} {card_text}"):
            continue

        job_id = title_link.attrs.get("data-jk") or ""
        if job_id and job_id in matched_ids:
            continue
        matched_ids.add(job_id)

        company_node = next(
            (
                element
                for element in elements
                if "companyName" in (element.attrs.get("class") or "").split()
                or element.attrs.get("data-testid") in {
                    "company-name",
                    "companyName",
                }
            ),
            None,
        )
        location_node = next(
            (
                element
                for element in elements
                if "companyLocation" in (element.attrs.get("class") or "").split()
                or element.attrs.get("data-testid") == "text-location"
            ),
            None,
        )
        snippet_node = next(
            (
                element
                for element in elements
                if "job-snippet" in (element.attrs.get("class") or "").split()
                or "jobMetaDataGroup" in (element.attrs.get("class") or "").split()
            ),
            None,
        )

        matching_jobs.append(
            {
                "job_id": job_id,
                "title": title,
                "company": company_node.text() if company_node else "",
                "location": location_node.text() if location_node else "",
                "search_result_url": urljoin(
                    source_url,
                    title_link.attrs.get("href") or "",
                ),
                "search_snippet": snippet_node.text() if snippet_node else "",
            }
        )

    selected_pane = None
    if panes:
        pane = panes[0]
        elements = list(_walk_elements(pane))
        title_node = next(
            (
                element for element in elements
                if element.attrs.get("data-testid") == "vj-job-title"
            ),
            None,
        )
        company_node = next(
            (
                element for element in elements
                if element.tag == "a"
                and "/cmp/" in (element.attrs.get("href") or "")
            ),
            None,
        )
        description_node = next(
            (
                element for element in elements
                if element.attrs.get("id") == "jobDetailsSection"
                or element.attrs.get("data-testid") == "viewjob-job-content"
            ),
            None,
        )

        action_roots = [
            element for element in elements
            if element.attrs.get("data-testid") in {
                "primary-apply-action",
                "viewjob-indeed-apply",
            }
        ]
        application_actions = []
        seen_actions = set()
        for action_root in action_roots:
            candidates = list(_walk_elements(action_root))
            for action in candidates:
                if action.tag not in {"a", "button"}:
                    continue
                label = action.text()
                href = action.attrs.get("href")
                if not label and not href:
                    continue
                action_url = urljoin(source_url, href) if href else None
                action_key = (label, action_url)
                if action_key in seen_actions:
                    continue
                seen_actions.add(action_key)
                application_actions.append(
                    {"label": label, "url": action_url}
                )

        selected_job_id = parse_qs(urlparse(source_url).query).get("vjk", [""])[0]
        selected_pane = {
            "job_id": selected_job_id,
            "title": title_node.text() if title_node else "",
            "company": company_node.text() if company_node else "",
            "description": description_node.text() if description_node else "",
            "application_actions": application_actions,
            "matches_keywords": _contains_target_keyword(
                title_node.text() if title_node else ""
            ),
        }

    return {
        "page_url": source_url,
        "matching_jobs": matching_jobs,
        "selected_pane": selected_pane,
    }


def _plain_text(value: str) -> str:
    parser = _DescriptionTextParser()
    parser.feed(value or "")
    return re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        " ".join(parser.parts),
    )


def _find_job_posting(value):
    if isinstance(value, list):
        for item in value:
            result = _find_job_posting(item)
            if result:
                return result

    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if "JobPosting" in types:
            return value

        for item in value.values():
            result = _find_job_posting(item)
            if result:
                return result

    return None


def _organization_name(value) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    if isinstance(value, list):
        return ", ".join(
            name
            for name in (_organization_name(item) for item in value)
            if name
        )
    return str(value or "")


def _location_text(value) -> list[str]:
    if isinstance(value, list):
        return [
            location
            for item in value
            for location in _location_text(item)
        ]

    if not isinstance(value, dict):
        return []

    address = value.get("address", value)
    if isinstance(address, list):
        return [
            location
            for item in address
            for location in _location_text(item)
        ]
    if not isinstance(address, dict):
        return []

    fields = (
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    )
    location = ", ".join(str(field) for field in fields if field)
    return [location] if location else []


async def _first_text(page, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count():
                text = await locator.inner_text(timeout=2_000)
                if text.strip():
                    return " ".join(text.split())
        except Exception:
            continue
    return ""


def _contains_target_keyword(value: str) -> bool:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return bool(
        re.search(r"\bqa\b", normalized)
        or "quality assurance" in normalized
        or re.search(r"\banalista\s+(?:de\s+)?qualidade\b", normalized)
    )


async def _application_actions(page, pane) -> list[dict[str, str | None]]:
    actions = pane.locator(
        "[data-testid='primary-apply-action'] a[href], "
        "[data-testid='primary-apply-action'] button, "
        "a[data-testid='viewjob-indeed-apply']"
    )
    found = []

    for index in range(await actions.count()):
        action = actions.nth(index)
        try:
            label = " ".join((await action.inner_text(timeout=1_000)).split())
            href = await action.get_attribute("href")
        except Exception:
            continue

        if label or href:
            found.append(
                {
                    "label": label,
                    "url": urljoin(page.url, href) if href else None,
                }
            )

    return found


async def _inspect_search_results(page) -> list[dict]:
    cards = page.locator(".cardOutline")
    matches = []
    seen_job_ids = set()

    for index in range(min(await cards.count(), 50)):
        card = cards.nth(index)
        title_link = card.locator("a.jcs-JobTitle[data-jk], a[data-jk]").first

        if not await title_link.count():
            continue

        try:
            title = " ".join((await title_link.inner_text(timeout=1_500)).split())
            job_id = await title_link.get_attribute("data-jk") or ""
            job_url = await title_link.get_attribute("href") or ""
            card_text = await card.inner_text(timeout=2_000)
        except Exception:
            continue

        if not _contains_target_keyword(card_text):
            continue

        if job_id and job_id in seen_job_ids:
            continue
        seen_job_ids.add(job_id)

        company = await _first_text(
            card,
            (
                "[data-testid='company-name']",
                ".companyName",
                "[data-testid='companyName']",
            ),
        )
        location = await _first_text(
            card,
            (
                "[data-testid='text-location']",
                ".companyLocation",
            ),
        )
        snippet = await _first_text(
            card,
            (
                "[data-testid*='snippet']",
                ".job-snippet",
                ".jobMetaDataGroup",
            ),
        )

        try:
            await title_link.click(timeout=5_000)
            pane = page.locator("[data-testid='viewjob-main-content']")
            await pane.wait_for(state="visible", timeout=10_000)
            try:
                await page.wait_for_function(
                    "expected => document.querySelector('[data-testid=\"vj-job-title\"]')?.innerText.includes(expected)",
                    arg=title,
                    timeout=8_000,
                )
            except Exception:
                pass

            selected_title = await _first_text(
                pane,
                ("[data-testid='vj-job-title']",),
            ) or title
            selected_company = await _first_text(
                pane,
                ("[data-testid='desktop-job-header'] a[href*='/cmp/']",),
            ) or company
            description = await _first_text(
                pane,
                (
                    "#jobDetailsSection",
                    "[data-testid='viewjob-job-content']",
                    "#jobDescriptionText",
                ),
            )
            application_actions = await _application_actions(page, pane)
        except Exception as error:
            selected_title = title
            selected_company = company
            description = ""
            application_actions = []
            print(f"Could not inspect Indeed result '{title}': {error}")

        matches.append(
            {
                "title": selected_title,
                "company": selected_company,
                "location": location,
                "search_result_url": urljoin(page.url, job_url),
                "description": description,
                "application_actions": application_actions,
                "search_snippet": snippet,
            }
        )

    return matches


def _is_verification_page(title: str, body: str, url: str) -> bool:
    page_text = f"{title} {body} {url}".casefold()
    indicators = (
        "additional verification required",
        "verify you are human",
        "checking if the site connection is secure",
        "security verification",
        "complete the security check",
        "captcha",
        "cloudflare",
    )
    return any(indicator in page_text for indicator in indicators)


async def _wait_for_manual_check(page):
    try:
        title = await page.title()
        body = await page.locator("body").inner_text(timeout=5_000)
    except PlaywrightError:
        print("Chrome was closed before the Indeed security check completed.")
        return False

    if not _is_verification_page(title, body, page.url):
        return True

    print(
        "Indeed requires a manual security check. Complete it in the open "
        "Chrome window; extraction will continue automatically."
    )

    deadline = time.monotonic() + MANUAL_CHECK_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            await page.wait_for_timeout(1_000)
            title = await page.title()
            body = await page.locator("body").inner_text(timeout=5_000)
        except PlaywrightError:
            print("Chrome was closed before the Indeed security check completed.")
            return False
        except Exception:
            continue

        if not _is_verification_page(title, body, page.url):
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=10_000)
            except Exception:
                pass
            print("Manual check cleared; continuing Indeed extraction.")
            return True

    print("Indeed manual verification timed out after five minutes.")
    return False


async def run(url: str):
    saved_html_path = Path(url).expanduser()
    if "://" not in url and saved_html_path.is_file():
        snapshot = _parse_saved_html(
            saved_html_path.read_text(encoding="utf-8", errors="replace")
        )
        snapshot["source_file"] = str(saved_html_path)
        print("Indeed saved HTML inspection (offline; no database writes):")
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError(f"Invalid Indeed job URL: {url}")

    if "indeed." not in parsed_url.netloc.casefold():
        raise ValueError(f"Expected an Indeed URL, got: {url}")

    INDEED_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(INDEED_PROFILE_DIR),
            channel="chrome",
            headless=False,
            chromium_sandbox=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=TIMEOUT,
            )
            if response and response.status == 403:
                print(
                    "Indeed returned HTTP 403. Stopping without retrying or "
                    "extracting blocked-page content."
                )
                return
            try:
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except Exception:
                pass

            if not await _wait_for_manual_check(page):
                return

            page_title = await page.title()
            if urlparse(page.url).path.rstrip("/").endswith("/jobs"):
                matches = await _inspect_search_results(page)
                print("Indeed QA search results (read-only; no database writes):")
                print(
                    json.dumps(
                        {
                            "page_url": page.url,
                            "page_title": page_title,
                            "matching_jobs": matches,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return

            structured_data = []
            scripts = page.locator('script[type="application/ld+json"]')
            for index in range(await scripts.count()):
                raw_json = await scripts.nth(index).text_content()
                if not raw_json:
                    continue
                try:
                    structured_data.append(json.loads(raw_json))
                except json.JSONDecodeError:
                    continue

            job_posting = next(
                (
                    posting
                    for item in structured_data
                    if (posting := _find_job_posting(item))
                ),
                {},
            )

            description = _plain_text(
                str(job_posting.get("description") or "")
            )
            if not description:
                description = await _first_text(
                    page,
                    (
                        "#jobDescriptionText",
                        "[data-testid='jobDescriptionText']",
                        "[class*='jobDescription']",
                    ),
                )

            links = []
            anchors = page.locator("a[href]")
            for index in range(min(await anchors.count(), 300)):
                anchor = anchors.nth(index)
                try:
                    href = await anchor.get_attribute("href")
                    text = " ".join((await anchor.inner_text(timeout=500)).split())
                except Exception:
                    continue

                if not href:
                    continue

                absolute_url = urljoin(page.url, href)
                if urlparse(absolute_url).scheme not in {"http", "https"}:
                    continue

                if any(
                    marker in (text + " " + absolute_url).casefold()
                    for marker in ("apply", "application", "job", "indeed")
                ):
                    links.append({"text": text, "url": absolute_url})

            job_data = {
                "page_url": page.url,
                "page_title": page_title,
                "title": job_posting.get("title") or await _first_text(
                    page,
                    (
                        "h1[data-testid='jobsearch-JobInfoHeader-title']",
                        "h1",
                    ),
                ),
                "company": _organization_name(
                    job_posting.get("hiringOrganization")
                ) or await _first_text(
                    page,
                    (
                        "[data-testid='inlineHeader-companyName']",
                        "[data-testid='companyName']",
                    ),
                ),
                "location": _location_text(
                    job_posting.get("jobLocation")
                ) or await _first_text(
                    page,
                    ("[data-testid='jobsearch-JobInfoHeader-companyLocation']",),
                ),
                "employment_type": job_posting.get("employmentType"),
                "date_posted": job_posting.get("datePosted"),
                "description": description,
                "links": links,
            }

            print("Indeed extraction (read-only; no database writes):")
            print(json.dumps(job_data, indent=2, ensure_ascii=False))

        finally:
            try:
                await context.close()
            except PlaywrightError:
                pass