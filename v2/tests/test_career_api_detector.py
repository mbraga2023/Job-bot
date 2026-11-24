"""Tests for career-page JSON API detection."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from v2.flows.careers import api_detector


class FakePlaywrightContext:
    def __init__(self, browser) -> None:
        self.browser = browser
        self.chromium = SimpleNamespace(launch=AsyncMock(return_value=browser))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def json_response(url: str, method: str = "GET"):
    return SimpleNamespace(
        headers={"content-type": "application/json; charset=utf-8"},
        request=SimpleNamespace(url=url, method=method),
    )


class TestCareerApiDetector(unittest.IsolatedAsyncioTestCase):
    async def test_detect_api_selects_highest_scoring_json_job_response(self) -> None:
        callbacks = []
        page = SimpleNamespace()
        page.on = MagicMock(side_effect=lambda _event, callback: callbacks.append(callback))
        responses = [
            SimpleNamespace(
                headers={"content-type": "text/html"},
                request=SimpleNamespace(url="https://careers.example/jobs", method="GET"),
            ),
            json_response("https://careers.example/api/jobs"),
            json_response("https://careers.example/api/job_search", "POST"),
            json_response("https://careers.example/api/jobs?tracking=pixel"),
        ]

        async def goto(_url, **_kwargs):
            for response in responses:
                await callbacks[0](response)

        page.goto = AsyncMock(side_effect=goto)

        candidate = await api_detector.CareerApiDetector().detect_api(
            page,
            "https://careers.example/careers",
        )

        self.assertEqual(candidate, {
            "url": "https://careers.example/api/job_search",
            "method": "POST",
            "score": 15,
        })
        page.on.assert_called_once_with("response", callbacks[0])
        page.goto.assert_awaited_once_with(
            "https://careers.example/careers",
            wait_until="networkidle",
            timeout=api_detector.config.timeout_ms,
        )

    async def test_detect_api_returns_none_for_irrelevant_or_malformed_responses(self) -> None:
        callbacks = []
        page = SimpleNamespace()
        page.on = MagicMock(side_effect=lambda _event, callback: callbacks.append(callback))

        class BrokenHeaders:
            def get(self, _key, _default):
                raise RuntimeError("malformed response")

        responses = [
            json_response("https://careers.example/api/account"),
            json_response("https://careers.example/api/jobs?tracking=1"),
            SimpleNamespace(headers=BrokenHeaders()),
        ]

        async def goto(_url, **_kwargs):
            for response in responses:
                await callbacks[0](response)
            raise RuntimeError("navigation failed")

        page.goto = AsyncMock(side_effect=goto)

        candidate = await api_detector.CareerApiDetector().detect_api(
            page,
            "https://careers.example/careers",
        )

        self.assertIsNone(candidate)

    async def test_run_detector_skips_sources_that_already_have_api_urls(self) -> None:
        sources = [{"id": 1, "api_url": "https://jobs.example/api"}]
        with (
            patch.object(api_detector, "get_active_career_sources", return_value=sources),
            patch.object(api_detector, "async_playwright") as start_browser,
        ):
            await api_detector.run_detector()

        start_browser.assert_not_called()

    async def test_run_detector_updates_only_sources_with_detected_apis(self) -> None:
        sources = [
            {"id": 1, "company": "Found", "careers_url": "https://found.example", "api_url": None},
            {"id": 2, "company": "Missing", "careers_url": "https://missing.example", "api_url": None},
            {"id": 3, "company": "Existing", "careers_url": "https://existing.example", "api_url": "/api"},
        ]
        page = SimpleNamespace()
        browser = SimpleNamespace(
            new_page=AsyncMock(return_value=page),
            close=AsyncMock(),
        )
        context = FakePlaywrightContext(browser)
        detector = SimpleNamespace(
            detect_api=AsyncMock(side_effect=[
                {"url": "https://found.example/api/jobs", "method": "GET", "score": 10},
                None,
            ])
        )

        with (
            patch.object(api_detector, "get_active_career_sources", return_value=sources),
            patch.object(api_detector, "async_playwright", return_value=context),
            patch.object(api_detector, "CareerApiDetector", return_value=detector),
            patch.object(api_detector, "update_source_api_info") as update_source,
        ):
            await api_detector.run_detector(limit=2)

        browser.new_page.assert_awaited_once_with()
        detector.detect_api.assert_has_awaits([
            call(page, "https://found.example"),
            call(page, "https://missing.example"),
        ])
        update_source.assert_called_once_with(
            1,
            api_url="https://found.example/api/jobs",
            api_method="GET",
        )
        browser.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
