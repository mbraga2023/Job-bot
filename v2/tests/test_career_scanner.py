"""Unit tests for career source scan scheduling and platform selection."""

from __future__ import annotations

import asyncio
import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from playwright.async_api import Error as PlaywrightError

from v2.flows.careers import scanner
from v2.flows.careers.adapters.base import CareerJobItem


class FakeBrowser:
    def __init__(self) -> None:
        self.pages: list[FakePage] = []
        self.page_options: list[dict] = []

    async def new_page(self, **options) -> FakePage:
        page = FakePage()
        self.pages.append(page)
        self.page_options.append(options)
        return page

    async def close(self) -> None:
        pass


class FakePage:
    def __init__(self) -> None:
        self.url = "about:blank"

    async def goto(self, *args, **kwargs) -> None:
        self.url = args[0]

    async def wait_for_timeout(self, _milliseconds: int) -> None:
        pass


class FakePlaywrightContext:
    def __init__(self) -> None:
        self.browser = FakeBrowser()
        self.chromium = self

    async def __aenter__(self) -> FakePlaywrightContext:
        return self

    async def __aexit__(self, *_args) -> None:
        pass

    async def launch(self, **_kwargs) -> FakeBrowser:
        return self.browser


class TestCareerScanner(unittest.TestCase):
    def test_navigation_retries_transient_dns_failures(self) -> None:
        page = type("Page", (), {})()
        page.url = "https://example.com/careers"
        page.goto = AsyncMock(
            side_effect=[
                PlaywrightError("net::ERR_NAME_NOT_RESOLVED"),
                None,
            ]
        )

        with patch.object(scanner.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            result = asyncio.run(
                scanner.navigate_to_source(page, "https://example.com/careers", 1000)
            )

        self.assertEqual(result, "https://example.com/careers")
        self.assertEqual(page.goto.await_count, 2)
        sleep.assert_awaited_once_with(1)

    def test_navigation_waits_for_redirect_when_superseded(self) -> None:
        page = type("Page", (), {})()
        page.url = "https://swa-carreiras.vagas.solides.com.br/"
        page.goto = AsyncMock(
            side_effect=PlaywrightError(
                'Navigation to "https://gruposysmap.gupy.io/" is interrupted by another navigation'
            )
        )
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        result = asyncio.run(
            scanner.navigate_to_source(page, "https://gruposysmap.gupy.io/", 1000)
        )

        self.assertEqual(result, page.url)
        page.wait_for_load_state.assert_awaited_once_with(
            "domcontentloaded",
            timeout=1000,
        )
        page.wait_for_timeout.assert_awaited_once_with(500)

    def test_recent_sources_are_skipped_and_search_all_includes_inhire(self) -> None:
        now = datetime.now(timezone.utc)
        sources = [
            {
                "id": 1,
                "company": "Recent InHire",
                "careers_url": "https://recent.inhire.app/careers",
                "last_checked_at": (now - timedelta(hours=23)).isoformat(),
            },
            {
                "id": 2,
                "company": "Old InHire",
                "careers_url": "https://old.inhire.app/careers",
                "last_checked_at": (now - timedelta(hours=25)).isoformat(),
            },
            {
                "id": 3,
                "company": "Generic",
                "careers_url": "https://example.com/careers",
                "last_checked_at": None,
            },
            {
                "id": 4,
                "company": "Errored InHire",
                "careers_url": "https://errored.inhire.app/careers",
                "last_checked_at": (now - timedelta(hours=1)).isoformat(),
                "last_error": "Previous scan failed",
            },
            {
                "id": 5,
                "company": "Mindsight",
                "careers_url": "https://oportunidades.mindsight.com.br/en/supernova",
                "last_checked_at": None,
            },
        ]
        inhire_adapter = type(
            "StubInHireAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
            },
        )()
        generic_adapter = type(
            "StubGenericAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
            },
        )()
        mindsight_adapter = type(
            "StubMindsightAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
            },
        )()
        playwright_context = FakePlaywrightContext()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=sources),
            patch.object(scanner, "async_playwright", return_value=playwright_context),
            patch.object(scanner, "InHireAdapter", return_value=inhire_adapter) as inhire,
            patch.object(scanner, "GenericAdapter", return_value=generic_adapter) as generic,
            patch.object(
                scanner,
                "MindsightAdapter",
                return_value=mindsight_adapter,
            ) as mindsight,
            patch.object(scanner, "insert_discovered_job"),
            patch.object(scanner, "mark_source_checked") as mark_checked,
        ):
            result = asyncio.run(scanner.run_scanner(platform="search_all"))

        self.assertEqual(result, {"discovered": 0, "new": 0})
        self.assertEqual(inhire.call_count, 2)
        self.assertEqual(generic.call_count, 1)
        self.assertEqual(
            [call.args[0] for call in mark_checked.call_args_list],
            [2, 3, 4, 5],
        )
        mindsight.assert_called_once()

    def test_mindsight_platform_only_scans_mindsight_sources(self) -> None:
        sources = [
            {
                "id": 1,
                "company": "Mindsight",
                "careers_url": "https://oportunidades.mindsight.com.br/en/supernova",
                "last_checked_at": None,
            },
            {
                "id": 2,
                "company": "Generic",
                "careers_url": "https://example.com/careers",
                "last_checked_at": None,
            },
        ]
        adapter = type(
            "StubMindsightAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
            },
        )()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=sources),
            patch.object(scanner, "async_playwright", return_value=FakePlaywrightContext()),
            patch.object(scanner, "MindsightAdapter", return_value=adapter) as mindsight,
            patch.object(scanner, "insert_discovered_job"),
            patch.object(scanner, "mark_source_checked") as mark_checked,
        ):
            result = asyncio.run(scanner.run_scanner(platform="mindsight"))

        self.assertEqual(result, {"discovered": 0, "new": 0})
        mindsight.assert_called_once()
        mark_checked.assert_called_once_with(1, discovered_jobs=0)

    def test_mindsight_url_detection(self) -> None:
        self.assertTrue(
            scanner.is_mindsight_url(
                "https://oportunidades.mindsight.com.br/en/supernova"
            )
        )
        self.assertFalse(scanner.is_mindsight_url("https://mindsight-careers.example.com"))

    def test_normalizes_locale_less_mindsight_urls(self) -> None:
        self.assertEqual(
            scanner.normalize_mindsight_url(
                "https://oportunidades.mindsight.com.br/supernova"
            ),
            "https://oportunidades.mindsight.com.br/en/supernova",
        )
        self.assertEqual(
            scanner.normalize_mindsight_url(
                "https://oportunidades.mindsight.com.br/en/supernova/"
            ),
            "https://oportunidades.mindsight.com.br/en/supernova/",
        )
        self.assertEqual(
            scanner.normalize_mindsight_url(
                "https://oportunidades.mindsight.com.br/pt/supernova?source=jobbot"
            ),
            "https://oportunidades.mindsight.com.br/pt/supernova?source=jobbot",
        )

    def test_search_all_normalizes_mindsight_source_before_navigation(self) -> None:
        source = {
            "id": 6,
            "company": "Supernova",
            "careers_url": "https://oportunidades.mindsight.com.br/supernova",
            "last_checked_at": None,
        }
        adapter = type(
            "StubMindsightAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
            },
        )()
        playwright_context = FakePlaywrightContext()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=[source]),
            patch.object(scanner, "async_playwright", return_value=playwright_context),
            patch.object(scanner, "MindsightAdapter", return_value=adapter),
            patch.object(scanner, "insert_discovered_job"),
            patch.object(scanner, "mark_source_checked"),
        ):
            result = asyncio.run(scanner.run_scanner(platform="search_all"))

        self.assertEqual(result, {"discovered": 0, "new": 0})
        self.assertEqual(
            playwright_context.browser.pages[1].url,
            "https://oportunidades.mindsight.com.br/en/supernova",
        )
        self.assertEqual(playwright_context.browser.page_options[1], {"locale": "en-US"})

    def test_conquestone_platform_only_scans_conquestone_sources(self) -> None:
        sources = [
            {
                "id": 1,
                "company": "Conquest One",
                "careers_url": (
                    "https://jobs.conquestone.com/jobboard.job.wpsearch.aspx"
                    "?CustomerID="
                ),
                "last_checked_at": None,
            },
            {
                "id": 2,
                "company": "Generic",
                "careers_url": "https://example.com/careers",
                "last_checked_at": None,
            },
        ]
        adapter = type(
            "StubConquestOneAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
            },
        )()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=sources),
            patch.object(scanner, "async_playwright", return_value=FakePlaywrightContext()),
            patch.object(
                scanner,
                "ConquestOneAdapter",
                return_value=adapter,
            ) as conquestone,
            patch.object(scanner, "insert_discovered_job"),
            patch.object(scanner, "mark_source_checked") as mark_checked,
        ):
            result = asyncio.run(scanner.run_scanner(platform="conquestone"))

        self.assertEqual(result, {"discovered": 0, "new": 0})
        conquestone.assert_called_once()
        mark_checked.assert_called_once_with(1, discovered_jobs=0)

    def test_conquestone_url_detection(self) -> None:
        self.assertTrue(
            scanner.is_conquestone_url(
                "https://jobs.conquestone.com/jobboard.job.wpsearch.aspx"
            )
        )
        self.assertFalse(
            scanner.is_conquestone_url("https://conquestone.example.com/careers")
        )

    def test_search_all_uses_conquestone_adapter(self) -> None:
        source = {
            "id": 3,
            "company": "Conquest One",
            "careers_url": (
                "https://jobs.conquestone.com/jobboard.job.wpsearch.aspx?CustomerID="
            ),
            "last_checked_at": None,
        }
        adapter = type(
            "StubConquestOneAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
            },
        )()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=[source]),
            patch.object(scanner, "async_playwright", return_value=FakePlaywrightContext()),
            patch.object(scanner, "ConquestOneAdapter", return_value=adapter) as conquestone,
            patch.object(scanner, "GenericAdapter") as generic,
            patch.object(scanner, "insert_discovered_job"),
            patch.object(scanner, "mark_source_checked"),
        ):
            result = asyncio.run(scanner.run_scanner(platform="search_all"))

        self.assertEqual(result, {"discovered": 0, "new": 0})
        conquestone.assert_called_once()
        generic.assert_not_called()

    def test_gupy_only_filters_sources_and_searches_each_term(self) -> None:
        sources = [
            {
                "id": 1,
                "company": "Gupy Example",
                "careers_url": "https://example.gupy.io/",
                "last_checked_at": None,
            },
            {
                "id": 2,
                "company": "Generic Example",
                "careers_url": "https://example.com/careers",
                "last_checked_at": None,
            },
        ]
        discovered = CareerJobItem(
            title="QA Engineer",
            url="https://example.gupy.io/job/123",
            company="Gupy Example",
        )
        adapter = type(
            "StubGupyAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(
                    side_effect=[[], [discovered], [discovered]],
                ),
                "search": AsyncMock(return_value=True),
            },
        )()
        output = io.StringIO()

        with (
            patch.object(
                scanner,
                "QA_SEARCH_TERMS",
                ["QA", "Quality Assurance", "Analista de Testes"],
            ),
            patch.object(scanner, "get_active_career_sources", return_value=sources),
            patch.object(scanner, "async_playwright", return_value=FakePlaywrightContext()),
            patch.object(scanner, "GupyAdapter", return_value=adapter) as gupy,
            patch.object(scanner, "insert_discovered_job", return_value=1) as insert_job,
            patch.object(scanner, "mark_source_checked") as mark_checked,
            redirect_stdout(output),
        ):
            result = asyncio.run(scanner.run_scanner(platform="gupy"))

        self.assertEqual(result, {"discovered": 1, "new": 1})
        gupy.assert_called_once()
        self.assertEqual(adapter.get_jobs.await_count, 3)
        self.assertEqual(
            [call.args[0] for call in adapter.search.await_args_list],
            ["QA", "Quality Assurance"],
        )
        insert_job.assert_called_once()
        mark_checked.assert_called_once_with(1, discovered_jobs=1)

    def test_future_or_invalid_check_timestamp_is_not_eligible(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertTrue(
            scanner.was_checked_within_24h({"id": 1, "last_checked_at": future.isoformat()})
        )
        self.assertTrue(
            scanner.was_checked_within_24h({"id": 2, "last_checked_at": "not-a-timestamp"})
        )

    def test_scan_logs_page_progress_and_inhire_search_attempts(self) -> None:
        source = {
            "id": 1,
            "company": "Example InHire",
            "careers_url": "https://example.inhire.app/careers",
            "last_checked_at": None,
        }
        adapter = type(
            "StubInHireAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(return_value=[]),
                "search": AsyncMock(return_value=False),
            },
        )()
        output = io.StringIO()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=[source]),
            patch.object(scanner, "async_playwright", return_value=FakePlaywrightContext()),
            patch.object(scanner, "InHireAdapter", return_value=adapter),
            patch.object(scanner, "insert_discovered_job"),
            patch.object(scanner, "mark_source_checked"),
            redirect_stdout(output),
        ):
            asyncio.run(scanner.run_scanner(platform="search_all"))

        logs = output.getvalue()
        self.assertIn("[PAGE] Opening https://example.inhire.app/careers", logs)
        self.assertIn("[INHIRE] Reading the job list", logs)
        self.assertIn("[SEARCH] Searching for 'QA'", logs)
        self.assertIn("[SEARCH] Search field not available for 'QA'", logs)
        self.assertIn("[SEARCH] Searching for 'Quality Assurance'", logs)
        adapter.search.assert_any_await("QA")
        adapter.search.assert_any_await("Quality Assurance")

    def test_scanner_does_not_insert_non_qa_or_untitled_items(self) -> None:
        source = {
            "id": 9,
            "company": "Example",
            "careers_url": "https://example.com/careers",
            "last_checked_at": None,
        }
        adapter = type(
            "StubGenericAdapter",
            (),
            {
                "wait_for_page_ready": AsyncMock(),
                "get_jobs": AsyncMock(
                    return_value=[
                        CareerJobItem(
                            title="Molder - Weekend Night Shift",
                            url="https://example.com/jobs/molder",
                        ),
                        CareerJobItem(
                            title="",
                            url="https://example.com/jobs/untitled",
                        ),
                        CareerJobItem(
                            title="QA Engineer",
                            url="https://example.com/jobs/qa-engineer",
                        ),
                    ]
                ),
            },
        )()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=[source]),
            patch.object(scanner, "async_playwright", return_value=FakePlaywrightContext()),
            patch.object(scanner, "GenericAdapter", return_value=adapter),
            patch.object(scanner, "insert_discovered_job") as insert_job,
            patch.object(scanner, "mark_source_checked"),
        ):
            asyncio.run(scanner.run_scanner(platform="search_all"))

        insert_job.assert_called_once()
        self.assertEqual(insert_job.call_args.kwargs["title"], "QA Engineer")


if __name__ == "__main__":
    unittest.main()
