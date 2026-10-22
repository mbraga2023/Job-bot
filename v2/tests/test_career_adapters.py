"""Unit tests for deterministic QA filtering during career discovery."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from v2.flows.careers.adapters.generic import GenericAdapter
from v2.flows.careers.adapters.gupy import GupyAdapter


class TestGenericAdapterFiltering(unittest.IsolatedAsyncioTestCase):
    async def test_requires_job_detail_url_and_qa_title_before_returning_job(self) -> None:
        adapter = GenericAdapter(AsyncMock())
        adapter.page.wait_for_load_state = AsyncMock()
        adapter.get_job_link_details = AsyncMock(
            return_value=[
                {
                    "url": "https://example.com/careers",
                    "title": "QA Engineer",
                },
                {
                    "url": "https://example.com/jobs/molder-weekend-night-shift",
                    "title": "Molder - Weekend Night Shift",
                },
                {
                    "url": "https://example.com/jobs/qa-engineer-pleno",
                    "title": "QA Engineer - Pleno",
                },
                {
                    "url": "https://example.com/jobs/qa-automation",
                    "title": "",
                },
            ]
        )

        jobs = await adapter.get_jobs("Example")

        self.assertEqual(
            [(job.title, job.url) for job in jobs],
            [
                (
                    "QA Engineer - Pleno",
                    "https://example.com/jobs/qa-engineer-pleno",
                ),
                (
                    "QA Automation",
                    "https://example.com/jobs/qa-automation",
                ),
            ],
        )


class TestGupyAdapterFiltering(unittest.IsolatedAsyncioTestCase):
    async def test_only_qa_job_cards_are_returned(self) -> None:
        adapter = GupyAdapter(AsyncMock())
        adapter.page.wait_for_load_state = AsyncMock()
        adapter.page.evaluate = AsyncMock()
        adapter.page.wait_for_timeout = AsyncMock()
        adapter.get_job_link_details = AsyncMock(
            return_value=[
                {
                    "url": "https://company.gupy.io/job/123",
                    "title": "Molder - Weekend Night Shift",
                },
                {
                    "url": "https://company.gupy.io/job/456",
                    "title": "QA Analyst",
                },
            ]
        )

        jobs = await adapter.get_jobs("Example")

        self.assertEqual([job.title for job in jobs], ["QA Analyst"])
        self.assertEqual(
            [job.url for job in jobs],
            ["https://company.gupy.io/job/456"],
        )


if __name__ == "__main__":
    unittest.main()
