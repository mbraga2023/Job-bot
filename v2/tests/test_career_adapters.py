"""Unit tests for deterministic QA filtering during career discovery."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from v2.flows.careers.adapters.base import BaseCareerAdapter, CareerPageModel
from v2.flows.careers.adapters.generic import GenericAdapter
from v2.flows.careers.adapters.gupy import GupyAdapter
from v2.flows.careers.adapters.conquestone import ConquestOneAdapter
from v2.flows.careers.adapters.inhire import InHireAdapter
from v2.flows.careers.adapters.mindsight import MindsightAdapter


class TestBaseCareerAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_visible_button_when_available(self) -> None:
        search_input = AsyncMock()
        search_input.first = search_input
        search_input.is_visible = AsyncMock(return_value=True)
        search_button = AsyncMock()
        search_button.first = search_button
        search_button.is_visible = AsyncMock(return_value=True)
        page = MagicMock()
        page.locator.side_effect = lambda selector: (
            search_input if selector == "#search" else search_button
        )
        page.wait_for_load_state = AsyncMock()
        adapter = BaseCareerAdapter(
            page,
            CareerPageModel(platform="test", search_input=["#search"], search_button=["#submit"]),
        )

        self.assertTrue(await adapter.search("QA"))

        search_input.fill.assert_awaited_once_with("QA")
        search_button.click.assert_awaited_once()
        page.wait_for_load_state.assert_awaited_once_with(
            "domcontentloaded",
            timeout=5000,
        )
        search_input.press.assert_not_awaited()

    async def test_search_falls_back_to_enter_then_returns_false_when_unavailable(self) -> None:
        hidden_input = AsyncMock()
        hidden_input.first = hidden_input
        hidden_input.is_visible = AsyncMock(return_value=False)
        enter_input = AsyncMock()
        enter_input.first = enter_input
        enter_input.is_visible = AsyncMock(return_value=True)
        enter_button = AsyncMock()
        enter_button.first = enter_button
        enter_button.is_visible = AsyncMock(return_value=False)
        page = MagicMock()
        page.locator.side_effect = lambda selector: {
            "#hidden": hidden_input,
            "#search": enter_input,
            "#submit": enter_button,
        }[selector]
        adapter = BaseCareerAdapter(
            page,
            CareerPageModel(
                platform="test",
                search_input=["#hidden", "#search"],
                search_button=["#submit"],
            ),
        )

        self.assertTrue(await adapter.search("QA"))
        enter_input.press.assert_awaited_once_with("Enter")

        enter_input.is_visible.side_effect = RuntimeError("selector failed")
        self.assertFalse(await adapter.search("QA"))

    async def test_get_job_links_keeps_unique_resolved_urls(self) -> None:
        first_link = SimpleNamespace(
            get_attribute=AsyncMock(return_value="/jobs/1"),
            evaluate=AsyncMock(return_value="https://example.com/jobs/1"),
        )
        empty_link = SimpleNamespace(get_attribute=AsyncMock(return_value=None))
        duplicate_link = SimpleNamespace(
            get_attribute=AsyncMock(return_value="/jobs/1"),
            evaluate=AsyncMock(return_value="https://example.com/jobs/1"),
        )
        first_selector = MagicMock()
        first_selector.count = AsyncMock(return_value=2)
        first_selector.nth = MagicMock(
            side_effect=lambda index: [first_link, empty_link][index]
        )
        second_selector = MagicMock()
        second_selector.count = AsyncMock(return_value=1)
        second_selector.nth = MagicMock(return_value=duplicate_link)
        page = MagicMock()
        page.locator.side_effect = lambda selector: (
            first_selector if selector == "a.primary" else second_selector
        )
        adapter = BaseCareerAdapter(
            page,
            CareerPageModel(platform="test", job_links=["a.primary", "a.fallback"]),
        )

        urls = await adapter.get_job_links()

        self.assertEqual(urls, ["https://example.com/jobs/1"])
        empty_link.get_attribute.assert_awaited_once_with("href")
        self.assertEqual(first_link.evaluate.await_count, 1)

    async def test_get_job_link_details_filters_invisible_links_and_fills_missing_title(self) -> None:
        page = MagicMock()
        links = MagicMock()
        links.evaluate_all = AsyncMock(side_effect=[
            [
                {"url": "https://example.com/jobs/1", "title": "", "visible": True},
                {"url": "https://example.com/jobs/hidden", "title": "QA", "visible": False},
                {"url": "", "title": "Missing URL", "visible": True},
            ],
            [
                {"url": "https://example.com/jobs/1", "title": "QA Engineer", "visible": True},
                {"url": "https://example.com/jobs/1", "title": "Other title", "visible": True},
            ],
        ])
        page.locator.return_value = links
        adapter = BaseCareerAdapter(
            page,
            CareerPageModel(platform="test", job_links=["a.primary", "a.fallback"]),
        )

        details = await adapter.get_job_link_details()

        self.assertEqual(details, [{"url": "https://example.com/jobs/1", "title": "QA Engineer"}])
        self.assertEqual(links.evaluate_all.await_count, 2)


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

    async def test_search_continues_after_hidden_and_timed_out_inputs(self) -> None:
        hidden_input = MagicMock()
        hidden_input.first.is_visible = AsyncMock(return_value=False)
        hidden_input.first.fill = AsyncMock()
        timed_out_input = MagicMock()
        timed_out_input.first.is_visible = AsyncMock(
            side_effect=PlaywrightTimeoutError("search timeout")
        )
        visible_input = MagicMock()
        visible_input.first.is_visible = AsyncMock(return_value=True)
        visible_input.first.fill = AsyncMock()
        visible_input.first.press = AsyncMock()
        page = MagicMock()
        page.locator.side_effect = [
            hidden_input,
            timed_out_input,
            visible_input,
        ]

        self.assertTrue(await GupyAdapter(page).search("QA"))

        hidden_input.first.fill.assert_not_awaited()
        visible_input.first.fill.assert_awaited_once_with("QA")
        visible_input.first.press.assert_awaited_once_with("Enter")

    async def test_get_jobs_ignores_invalid_duplicate_and_non_qa_links(self) -> None:
        page = MagicMock()
        page.wait_for_load_state = AsyncMock(
            side_effect=PlaywrightTimeoutError("load timeout")
        )
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        adapter = GupyAdapter(page)
        adapter.get_job_link_details = AsyncMock(return_value=[
            {"url": "https://company.gupy.io/job/open", "title": "QA Engineer"},
            {"url": "https://company.gupy.io/job/456", "title": "Molder"},
            {"url": "https://company.gupy.io/job/123", "title": "QA Engineer"},
            {"url": "https://company.gupy.io/job/123", "title": "QA Engineer Pleno"},
        ])

        jobs = await adapter.get_jobs("Example")

        self.assertEqual(
            [(job.title, job.url) for job in jobs],
            [("QA Engineer", "https://company.gupy.io/job/123")],
        )
        page.wait_for_load_state.assert_awaited_once_with(
            "networkidle",
            timeout=8_000,
        )
        self.assertEqual(page.evaluate.await_count, 5)
        self.assertEqual(page.wait_for_timeout.await_count, 5)


class TestMindsightAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_wait_search_and_pagination_handle_timeout_or_missing_page(self) -> None:
        page = MagicMock()
        listing = MagicMock()
        listing.first.wait_for = AsyncMock(
            side_effect=PlaywrightTimeoutError("listing timeout")
        )
        search_input = MagicMock()
        search_input.first.is_visible = AsyncMock(
            side_effect=PlaywrightTimeoutError("search timeout")
        )
        page.locator.side_effect = lambda selector: (
            listing
            if selector == 'a[href*="/supernova/"]'
            else search_input
        )
        adapter = MindsightAdapter(page)

        await adapter.wait_for_page_ready()
        self.assertFalse(await adapter.search("QA"))
        search_input.first.is_visible = AsyncMock(return_value=False)
        self.assertFalse(await adapter.search("QA"))

        page.wait_for_load_state = AsyncMock(
            side_effect=PlaywrightTimeoutError("load timeout")
        )
        links = MagicMock()
        links.evaluate_all = AsyncMock(return_value=[])
        next_page = MagicMock()
        next_page.is_disabled = AsyncMock(return_value=False)
        next_page.click = AsyncMock()
        active_page = MagicMock()
        active_page.get_attribute = AsyncMock(return_value=None)
        page.locator.side_effect = lambda selector: (
            links
            if selector == 'a[href*="/supernova/"]'
            else next_page
            if selector == "li.ant-pagination-next button"
            else active_page
        )

        self.assertEqual(await adapter.get_jobs(), [])
        page.wait_for_load_state.assert_awaited_once_with(
            "domcontentloaded",
            timeout=10_000,
        )
        next_page.click.assert_not_awaited()

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
    async def test_wait_search_and_pagination_handle_timeout_or_missing_controls(self) -> None:
        page = MagicMock()
        listing = MagicMock()
        listing.first.wait_for = AsyncMock(
            side_effect=PlaywrightTimeoutError("listing timeout")
        )
        search_input = MagicMock()
        search_input.first.is_visible = AsyncMock(return_value=False)
        adapter = ConquestOneAdapter(page)
        page.locator.side_effect = lambda selector: (
            listing
            if selector == adapter.model.job_links[0]
            else search_input
        )

        await adapter.wait_for_page_ready()
        self.assertFalse(await adapter.search("QA"))

        search_input.first.is_visible = AsyncMock(return_value=True)
        search_input.first.fill = AsyncMock(
            side_effect=PlaywrightTimeoutError("fill timeout")
        )
        self.assertFalse(await adapter.search("QA"))

        page.wait_for_load_state = AsyncMock(
            side_effect=PlaywrightTimeoutError("load timeout")
        )
        links = MagicMock()
        links.evaluate_all = AsyncMock(return_value=[])
        next_page = MagicMock()
        next_page.count = AsyncMock(return_value=1)
        next_page.get_attribute = AsyncMock(return_value="next")
        active_page = MagicMock()
        active_page.count = AsyncMock(return_value=0)
        page.locator.side_effect = lambda selector: (
            links
            if selector == adapter.model.job_links[0]
            else next_page
            if selector == "#UCPAGINATIONBARContainer li.next"
            else active_page
        )

        self.assertEqual(await adapter.get_jobs(), [])
        page.wait_for_load_state.assert_awaited_once_with(
            "domcontentloaded",
            timeout=10_000,
        )
        page.locator.assert_any_call("#UCPAGINATIONBARContainer li.active")

        next_page.count = AsyncMock(return_value=0)
        links.evaluate_all = AsyncMock(return_value=[])
        page.wait_for_load_state = AsyncMock(
            side_effect=PlaywrightTimeoutError("load timeout")
        )
        self.assertEqual(await adapter.get_jobs(), [])

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


class TestInHireAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_wait_for_page_ready_ignores_listing_timeout(self) -> None:
        page = MagicMock()
        locator = MagicMock()
        locator.first.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        page.locator.return_value = locator

        await InHireAdapter(page).wait_for_page_ready()

        locator.first.wait_for.assert_awaited_once_with(state="visible", timeout=12_000)

    async def test_get_jobs_stops_after_stable_scroll_and_filters_invalid_listings(self) -> None:
        heights = iter([1000, 1100, 1200, 1300, 1300, 1300, 1300])

        async def evaluate(script: str):
            if "scrollTo" in script:
                return None
            return next(heights)

        page = MagicMock()
        page.evaluate = AsyncMock(side_effect=evaluate)
        page.wait_for_timeout = AsyncMock()
        links = MagicMock()
        links.count = AsyncMock(return_value=2)
        links.evaluate_all = AsyncMock(return_value=[
            {
                "url": "https://jobs.inhire.app/vagas/qa/123",
                "title": "  QA   Engineer  ",
                "visible": True,
            },
            {
                "url": "https://jobs.inhire.app/vagas/qa/123",
                "title": "Duplicate",
                "visible": True,
            },
            {
                "url": "https://jobs.inhire.app/vagas/qa/hidden",
                "title": "Hidden QA",
                "visible": False,
            },
            {
                "url": "https://jobs.inhire.app/vagas/short",
                "title": "Short path",
                "visible": True,
            },
            {
                "url": "https://jobs.inhire.app/jobs/qa/456",
                "title": "Wrong path",
                "visible": True,
            },
            {
                "url": "https://jobs.inhire.app/vagas/qa/empty",
                "title": "",
                "visible": True,
            },
            {
                "url": "https://jobs.inhire.app/vagas/qa/label",
                "title": "See the jobs",
                "visible": True,
            },
        ])
        page.locator.return_value = links

        jobs = await InHireAdapter(page).get_jobs("Example")

        self.assertEqual(
            [(job.title, job.url, job.company) for job in jobs],
            [("QA Engineer", "https://jobs.inhire.app/vagas/qa/123", "Example")],
        )
        self.assertEqual(links.count.await_count, 7)
        self.assertEqual(page.wait_for_timeout.await_count, 7)


if __name__ == "__main__":
    unittest.main()
