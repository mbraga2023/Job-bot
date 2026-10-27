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

    def test_non_easy_apply_updates_application_url_from_apply_link(self) -> None:
        job = {
            "id": 4475564872,
            "source_url": (
                "https://www.linkedin.com/jobs/view/"
                "pl-engenharia-de-automa%C3%A7%C3%A3o-de-testes-at-%C3%ADlia-4475564872/"
            ),
            "application_url": None,
            "company": "Example",
            "title": "PL Engenharia de Automação de Testes",
        }
        application_url = (
            "https://www.linkedin.com/safety/go/?url="
            "https%3A%2F%2Fjob-boards.greenhouse.io%2Filia%2Fjobs%2F6211264004"
            "&urlhash=Sbsu&mt=9oV84o6xbzFW0Lo_L-r5ZS9NIyK4Mhgoqtpx10ZjVJmT6FnpTDR21_lUhjvi9DmGwdOWCW3UFUNDdxaCxMJ0Y0mcsxY"
            "&isSdui=true&lipi=urn%3Ali%3Apage%3Ad_flagship3_job_details%3BkjeXYXgPT8%2BwVNE5lO%2FXAg%3D%3D"
        )
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=None)
        cursor = Mock()
        cursor.fetchall.return_value = [job]
        connection.execute.return_value = cursor
        analyzer = Mock()
        analyzer.analyze = AsyncMock(return_value={
            "job_status": "OPEN",
            "easy_apply": False,
            "remote": True,
        })
        analyzer.get_application_url = AsyncMock(return_value=application_url)
        playwright_context = FakePlaywrightContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(linkedin, "get_connection", return_value=connection),
                patch.object(linkedin, "async_playwright", return_value=playwright_context),
                patch.object(linkedin, "LinkedInAnalyzer", return_value=analyzer),
                patch.object(linkedin, "update_job_validation") as update,
                patch.object(config, "linkedin_profile_dir", Path(temp_dir)),
                patch.object(config, "headless", True),
                patch.object(config, "timeout_ms", 1000),
                patch.object(linkedin.asyncio, "sleep", new_callable=AsyncMock),
            ):
                asyncio.run(linkedin.run_linkedin_validator(limit=1))

        update.assert_called_once_with(
            job_id=4475564872,
            status="OPEN",
            application_url=application_url,
            remote=1,
        )
        analyzer.get_application_url.assert_awaited_once_with(playwright_context.page)


if __name__ == "__main__":
    unittest.main()
