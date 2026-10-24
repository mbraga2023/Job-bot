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
