"""Tests for LinkedIn job status and workplace detection."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock

from v2.flows.telegram.analyzers.linkedin import LinkedInAnalyzer, is_linkedin_person_url
from v2.flows.telegram.parser import is_remote_job


class TestLinkedInAnalyzer(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.analyzer = LinkedInAnalyzer()

    async def test_missing_workplace_mode_is_open_but_not_confirmed_remote(self) -> None:
        page = Mock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.locator.return_value.inner_text = AsyncMock(return_value="QA Engineer")

        self.analyzer._detect_workplace = AsyncMock(return_value=None)
        self.analyzer._has_easy_apply = AsyncMock(return_value=False)

        result = await self.analyzer.analyze(page)

        self.assertEqual(result["job_status"], "OPEN")
        self.assertIsNone(result["remote"])

    async def test_analyze_reports_easy_apply_button(self) -> None:
        page = Mock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.locator.return_value.inner_text = AsyncMock(return_value="QA Engineer")
        self.analyzer._detect_workplace = AsyncMock(return_value=None)
        self.analyzer._has_easy_apply = AsyncMock(return_value=True)

        result = await self.analyzer.analyze(page)

        self.assertTrue(result["easy_apply"])

    async def test_easy_apply_detection_falls_back_to_button_text(self) -> None:
        empty_locator = Mock()
        empty_locator.count = AsyncMock(return_value=0)
        page = Mock()
        page.locator.side_effect = [empty_locator, empty_locator, empty_locator]
        easy_apply_button = Mock()
        easy_apply_button.count = AsyncMock(return_value=1)
        easy_apply_button.nth.return_value.is_visible = AsyncMock(return_value=True)
        page.get_by_role.return_value = easy_apply_button

        detected = await self.analyzer._has_easy_apply(page)

        self.assertTrue(detected)
        page.get_by_role.assert_called_once()

    async def test_application_url_skips_linkedin_job_recommendations(self) -> None:
        page = Mock(url="https://www.linkedin.com/jobs/view/123")
        links = Mock()
        links.count = AsyncMock(return_value=2)
        links.nth.return_value.get_attribute = AsyncMock(
            side_effect=[
                "/jobs/search-results/?currentJobId=456",
                "https://apply.example.com/jobs/123",
            ]
        )
        page.get_by_role.return_value = links

        application_url = await self.analyzer.get_application_url(page)

        self.assertEqual(application_url, "https://apply.example.com/jobs/123")

    def test_workplace_detection_excludes_hybrid_and_onsite(self) -> None:
        for workplace in ("hybrid", "híbrido", "onsite", "on-site", "presencial"):
            with self.subTest(workplace=workplace):
                self.assertEqual(
                    self.analyzer._classify_workplace(workplace),
                    "NOT_REMOTE",
                )

    def test_workplace_detection_identifies_remote(self) -> None:
        self.assertEqual(
            self.analyzer._classify_workplace("Remote - Brazil"),
            "REMOTE",
        )

    def test_telegram_remote_classification_rejects_mixed_workplace_modes(self) -> None:
        self.assertEqual(
            is_remote_job({"description": "Remote, hybrid schedule"}),
            0,
        )
        self.assertEqual(
            is_remote_job({"location": "Presencial; remote opportunities"}),
            0,
        )
        self.assertEqual(is_remote_job({"location": "Remote"}), 1)

    def test_linkedin_person_url_detection(self) -> None:
        for url in (
            "https://ca.linkedin.com/in/some-name",
            "https://www.linkedin.com/in/some-name/",
            "https://www.linkedin.com/in/some-name/details/experience/",
        ):
            with self.subTest(url=url):
                self.assertTrue(is_linkedin_person_url(url))

        for url in (
            "https://www.linkedin.com/jobs/view/123",
            "https://example.com/in/some-name",
            "https://linkedin.com/in/",
            None,
        ):
            with self.subTest(url=url):
                self.assertFalse(is_linkedin_person_url(url))


if __name__ == "__main__":
    unittest.main()
