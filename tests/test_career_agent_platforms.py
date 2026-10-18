from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.career_agent import CareerAgent
from core.career_result import CareerJob


class CareerAgentPlatformTests(unittest.IsolatedAsyncioTestCase):
    def test_inhire_source_matching_requires_inhire_app_hostname(self):
        self.assertTrue(
            CareerAgent.is_inhire_source("https://zallpy.inhire.app/vagas")
        )
        self.assertTrue(CareerAgent.is_inhire_source("https://inhire.app/vagas"))
        self.assertFalse(
            CareerAgent.is_inhire_source("https://example.com/inhire.app/vagas")
        )
        self.assertFalse(
            CareerAgent.is_inhire_source("https://notinhire.app/vagas")
        )

    def test_invalid_platform_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported career platform"):
            CareerAgent(platform="unknown")

    def test_search_all_is_the_existing_default(self):
        self.assertEqual(CareerAgent().platform, "search_all")

    def test_checked_within_24_hours_is_skipped(self):
        now = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
        source = {
            "company": "InHire Co",
            "last_checked_at": (now - timedelta(hours=23)).isoformat(),
        }

        self.assertTrue(CareerAgent.was_checked_within_last_day(source, now))

    def test_checked_exactly_24_hours_ago_is_skipped(self):
        now = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
        source = {
            "company": "InHire Co",
            "last_checked_at": (now - timedelta(hours=24)).isoformat(),
        }

        self.assertTrue(CareerAgent.was_checked_within_last_day(source, now))

    def test_missing_or_older_check_timestamp_is_not_skipped(self):
        now = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
        self.assertFalse(
            CareerAgent.was_checked_within_last_day(
                {"company": "Never checked", "last_checked_at": None},
                now,
            )
        )
        self.assertFalse(
            CareerAgent.was_checked_within_last_day(
                {
                    "company": "Old check",
                    "last_checked_at": (now - timedelta(hours=24, seconds=1)).isoformat(),
                },
                now,
            )
        )

    def test_invalid_check_timestamp_logs_warning_and_is_not_skipped(self):
        with patch("agents.career_agent.print") as print_mock:
            should_skip = CareerAgent.was_checked_within_last_day(
                {"company": "Invalid date", "last_checked_at": "not-a-date"}
            )

        self.assertFalse(should_skip)
        print_mock.assert_called_once()
        self.assertIn("Could not parse last_checked_at", print_mock.call_args.args[0])

    @patch("agents.career_agent.get_career_sources")
    @patch("agents.career_agent.async_playwright")
    async def test_inhire_run_only_processes_inhire_sources(
        self,
        playwright_factory,
        get_sources,
    ):
        get_sources.return_value = [
            {
                "id": 1,
                "company": "InHire Co",
                "careers_url": "https://inhire-company.inhire.app/vagas",
                "last_checked_at": None,
            },
            {
                "id": 2,
                "company": "Other Co",
                "careers_url": "https://example.com/careers",
                "last_checked_at": None,
            },
            {
                "id": 3,
                "company": "Recently checked",
                "careers_url": "https://recent.inhire.app/vagas",
                "last_checked_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        agent = CareerAgent(platform="inhire")
        agent.check_source = AsyncMock()
        browser = MagicMock()
        browser.close = AsyncMock()
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)
        playwright.stop = AsyncMock()
        playwright_factory.return_value.start = AsyncMock(
            return_value=playwright
        )

        await agent.run()

        agent.check_source.assert_awaited_once_with(
            source=get_sources.return_value[0],
            index=1,
            total=1,
            browser=browser,
        )
        browser.close.assert_awaited_once()
        playwright.stop.assert_awaited_once()

    async def test_inhire_analysis_filters_all_loaded_jobs_without_searching(self):
        page = MagicMock()
        agent = CareerAgent(platform="inhire")
        adapter = MagicMock()
        adapter.wait_for_page_ready = AsyncMock()
        adapter.get_jobs = AsyncMock(
            return_value=[
                CareerJob(title="QA Engineer", url="https://jobs/1"),
                CareerJob(title="Software Developer", url="https://jobs/2"),
                CareerJob(title="Quality Engineer", url="https://jobs/3"),
                CareerJob(title="SDET", url="https://jobs/4"),
            ]
        )
        adapter.search = AsyncMock()

        with patch("agents.career_agent.InHireAdapter", return_value=adapter):
            result = await agent.analyze_inhire_page(page)

        adapter.wait_for_page_ready.assert_awaited_once_with()
        adapter.get_jobs.assert_awaited_once_with()
        adapter.search.assert_not_awaited()
        self.assertEqual(
            [job.title for job in result.jobs],
            ["QA Engineer", "Quality Engineer", "SDET"],
        )
        self.assertEqual(
            [job.url for job in result.jobs],
            ["https://jobs/1", "https://jobs/3", "https://jobs/4"],
        )
        self.assertIn("loaded job listings", result.message)
