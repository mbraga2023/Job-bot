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


class FakeBrowser:
    def __init__(self) -> None:
        self.page = FakePage()

    async def new_page(self) -> FakePage:
        return self.page

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
        playwright_context = FakePlaywrightContext()

        with (
            patch.object(scanner, "get_active_career_sources", return_value=sources),
            patch.object(scanner, "async_playwright", return_value=playwright_context),
            patch.object(scanner, "InHireAdapter", return_value=inhire_adapter) as inhire,
            patch.object(scanner, "GenericAdapter", return_value=generic_adapter) as generic,
            patch.object(scanner, "insert_discovered_job"),
            patch.object(scanner, "mark_source_checked") as mark_checked,
        ):
            result = asyncio.run(scanner.run_scanner(platform="search_all"))

        self.assertEqual(result, {"discovered": 0, "new": 0})
        self.assertEqual(inhire.call_count, 2)
        self.assertEqual(generic.call_count, 1)
        self.assertEqual(
            [call.args[0] for call in mark_checked.call_args_list],
            [2, 3, 4],
        )

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


if __name__ == "__main__":
    unittest.main()
