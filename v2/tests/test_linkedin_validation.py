"""Tests for LinkedIn job validation status updates."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from v2.config import config
from v2.flows.telegram import linkedin


class FakePlaywrightContext:
    def __init__(self) -> None:
        self.page = SimpleNamespace(
            url="https://www.linkedin.com/jobs/view/123",
            goto=AsyncMock(),
        )
        self.browser_context = SimpleNamespace(
            pages=[self.page],
            close=AsyncMock(),
        )
        self.chromium = SimpleNamespace(
            launch_persistent_context=AsyncMock(return_value=self.browser_context),
        )

    async def __aenter__(self):
        return SimpleNamespace(chromium=self.chromium)

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass


class TestLinkedInValidation(unittest.TestCase):
    def test_easy_apply_sets_status_without_fetching_application_url(self) -> None:
        job = {
            "id": 123,
            "source_url": "https://www.linkedin.com/jobs/view/123",
            "application_url": "https://www.linkedin.com/jobs/view/123",
            "company": "Example",
            "title": "QA Engineer",
        }
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=None)
        cursor = Mock()
        cursor.fetchall.return_value = [job]
        connection.execute.return_value = cursor
        analyzer = Mock()
        analyzer.analyze = AsyncMock(return_value={
            "job_status": "OPEN",
            "easy_apply": True,
            "remote": False,
        })
        analyzer.get_application_url = AsyncMock(return_value="https://wrong.example/")

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(linkedin, "get_connection", return_value=connection),
                patch.object(linkedin, "async_playwright", return_value=FakePlaywrightContext()),
                patch.object(linkedin, "LinkedInAnalyzer", return_value=analyzer),
                patch.object(linkedin, "update_job_validation") as update,
                patch.object(config, "linkedin_profile_dir", Path(temp_dir)),
                patch.object(config, "headless", True),
                patch.object(config, "timeout_ms", 1000),
                patch.object(linkedin.asyncio, "sleep", new_callable=AsyncMock),
            ):
                asyncio.run(linkedin.run_linkedin_validator(limit=1))

        update.assert_called_once_with(job_id=123, status="EASY_APPLY", remote=0)
        analyzer.get_application_url.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
