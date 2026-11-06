"""Unit tests for deterministic QA filtering during career discovery."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from v2.flows.careers.adapters.generic import GenericAdapter
from v2.flows.careers.adapters.gupy import GupyAdapter
from v2.flows.careers.adapters.conquestone import ConquestOneAdapter
from v2.flows.careers.adapters.mindsight import MindsightAdapter


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
    async def test_search_fills_gupy_field_and_presses_enter(self) -> None:
        locator = type(
            "SearchLocator",
            (),
            {
                "first": None,
                "is_visible": AsyncMock(return_value=True),
                "fill": AsyncMock(),
                "press": AsyncMock(),
                "click": AsyncMock(),
            },
        )()
        locator.first = locator
        page = MagicMock()
        page.locator.return_value = locator
        adapter = GupyAdapter(page)

        searched = await adapter.search("Quality Assurance")

        self.assertTrue(searched)
        page.locator.assert_called_once_with("#job-search-input")
        locator.fill.assert_awaited_once_with("Quality Assurance")
        locator.press.assert_awaited_once_with("Enter")
        locator.click.assert_not_awaited()

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


class TestMindsightAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_qa_jobs_across_pages(self) -> None:
        page = MagicMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_function = AsyncMock()
        links = AsyncMock()
        links.evaluate_all = AsyncMock(
            side_effect=[
                [
                    {
                        "url": "https://oportunidades.mindsight.com.br/supernova/75/",
                        "title": "Analista de Testes / QA (Quality Assurance)",
                        "location": "São Paulo, São Paulo, Brazil",
                    },
                    {
                        "url": "https://oportunidades.mindsight.com.br/supernova/76/",
                        "title": "Líder Financeiro",
                        "location": "São Paulo, São Paulo, Brazil",
                    },
                ],
                [
                    {
                        "url": "https://oportunidades.mindsight.com.br/supernova/72/",
                        "title": "QA Engineer",
                        "location": "Remote",
                    },
                ],
            ]
        )
        next_page = AsyncMock()
        next_page.is_disabled = AsyncMock(side_effect=[False, True])
        active_page = AsyncMock()
        active_page.get_attribute = AsyncMock(return_value="1")

        def locate(selector: str):
            if selector == 'a[href*="/supernova/"]':
                return links
            if selector == "li.ant-pagination-next button":
                return next_page
            if selector == ".ant-pagination-item-active":
                return active_page
            raise AssertionError(f"Unexpected selector: {selector}")

        page.locator.side_effect = locate
        adapter = MindsightAdapter(page)

        jobs = await adapter.get_jobs("Supernova")

        self.assertEqual(
            [(job.title, job.external_id, job.location) for job in jobs],
            [
                (
                    "Analista de Testes / QA (Quality Assurance)",
                    "75",
                    "São Paulo, São Paulo, Brazil",
                ),
                ("QA Engineer", "72", "Remote"),
            ],
        )
        next_page.click.assert_awaited_once()
        page.wait_for_function.assert_awaited_once()

    async def test_search_submits_job_title_query(self) -> None:
        search_input = AsyncMock()
        search_input.first = search_input
        search_input.is_visible = AsyncMock(return_value=True)
        search_button = AsyncMock()
        page = MagicMock()
        page.locator.side_effect = lambda selector: (
            search_input
            if selector == 'input[placeholder="Search job title"]'
            else search_button
        )

        searched = await MindsightAdapter(page).search("QA")

        self.assertTrue(searched)
        search_input.fill.assert_awaited_once_with("QA")
        search_button.click.assert_awaited_once()


class TestConquestOneAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_qa_jobs_across_pages(self) -> None:
        page = MagicMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_function = AsyncMock()
        links = AsyncMock()
        links.evaluate_all = AsyncMock(
            side_effect=[
                [
                    {
                        "url": (
                            "https://jobs.conquestone.com/jobboard.job.wpdetails.aspx"
                            "?id=d38a4270-ed43-4bb3-9b80-31cd86699898&CustomerID="
                        ),
                        "title": "Banco de Talentos QA / Testes",
                        "location": "São Paulo, Brasil",
                    },
                    {
                        "url": (
                            "https://jobs.conquestone.com/jobboard.job.wpdetails.aspx"
                            "?id=12345678-1234-1234-1234-123456789012&CustomerID="
                        ),
                        "title": "Engenheiro de Dados",
                        "location": "São Paulo, Brasil",
                    },
                ],
                [
                    {
                        "url": (
                            "https://jobs.conquestone.com/jobboard.job.wpdetails.aspx"
                            "?id=7d97450d-a9c9-4f31-aef2-c3740cfee730&CustomerID="
                        ),
                        "title": "Analista de Qualidade de Software (QA)",
                        "location": "São Paulo, Brasil",
                    },
                ],
            ]
        )
        next_page = AsyncMock()
        next_page.get_attribute = AsyncMock(side_effect=["next", "next disabled"])
        next_link = AsyncMock()
        active_page = AsyncMock()
        active_page.inner_text = AsyncMock(side_effect=["1", "2"])

        def locate(selector: str):
            if 'a[href*="jobboard.job.wpdetails.aspx"]' in selector:
                return links
            if selector == "#UCPAGINATIONBARContainer li.next":
                return next_page
            if selector == "#UCPAGINATIONBARContainer li.next a":
                return next_link
            if selector == "#UCPAGINATIONBARContainer li.active":
                return active_page
            raise AssertionError(f"Unexpected selector: {selector}")

        page.locator.side_effect = locate
        adapter = ConquestOneAdapter(page)

        jobs = await adapter.get_jobs("Conquest One")

        self.assertEqual(
            [(job.title, job.external_id, job.location) for job in jobs],
            [
                (
                    "Banco de Talentos QA / Testes",
                    "d38a4270-ed43-4bb3-9b80-31cd86699898",
                    "São Paulo, Brasil",
                ),
                (
                    "Analista de Qualidade de Software (QA)",
                    "7d97450d-a9c9-4f31-aef2-c3740cfee730",
                    "São Paulo, Brasil",
                ),
            ],
        )
        next_link.click.assert_awaited_once()
        page.wait_for_function.assert_awaited_once()

    async def test_search_submits_job_title(self) -> None:
        search_input = AsyncMock()
        search_input.first = search_input
        search_input.is_visible = AsyncMock(return_value=True)
        search_button = AsyncMock()
        page = MagicMock()
        page.locator.side_effect = lambda selector: (
            search_input if selector == "#vMATCHTEXT" else search_button
        )

        searched = await ConquestOneAdapter(page).search("QA")

        self.assertTrue(searched)
        search_input.fill.assert_awaited_once_with("QA")
        search_button.click.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
