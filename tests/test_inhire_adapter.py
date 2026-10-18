import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.platforms.base import BaseCareerAdapter
from agents.platforms.inhire import INHIRE_MODEL, InHireAdapter


class InHireAdapterUnitTests(unittest.IsolatedAsyncioTestCase):
    def test_adapter_uses_the_base_career_adapter(self):
        adapter = InHireAdapter(MagicMock())

        self.assertIsInstance(adapter, BaseCareerAdapter)
        self.assertEqual(adapter.model.platform, "inhire")
        self.assertIn('a[href^="/vagas/"]', adapter.model.job_links)
        self.assertIn('li:has(a[href^="/vagas/"])', adapter.model.job_cards)

    async def test_search_fills_the_configured_input_and_submits_with_enter(self):
        page = MagicMock()
        search_input = MagicMock()
        search_input.is_visible = AsyncMock(return_value=True)
        search_input.fill = AsyncMock()
        search_input.press = AsyncMock()
        page.locator.return_value.first = search_input
        adapter = InHireAdapter(page)

        found = await adapter.search("Quality Assurance")

        self.assertTrue(found)
        page.locator.assert_called_once_with("input#name")
        search_input.fill.assert_awaited_once_with("Quality Assurance")
        search_input.press.assert_awaited_once_with("Enter")

    async def test_job_links_returns_unique_absolute_urls(self):
        page = MagicMock()
        links = MagicMock()
        links.count = AsyncMock(return_value=3)
        page.locator.return_value = links

        first_link = MagicMock()
        first_link.get_attribute = AsyncMock(return_value="/vagas/role-a")
        first_link.evaluate = AsyncMock(
            return_value="https://mblabs.inhire.app/vagas/role-a"
        )
        duplicate_link = MagicMock()
        duplicate_link.get_attribute = AsyncMock(return_value="/vagas/role-a")
        duplicate_link.evaluate = AsyncMock(
            return_value="https://mblabs.inhire.app/vagas/role-a"
        )
        empty_link = MagicMock()
        empty_link.get_attribute = AsyncMock(return_value=None)
        link_locators = [first_link, duplicate_link, empty_link]
        links.nth.side_effect = lambda index: link_locators[index]
        adapter = InHireAdapter(page)

        urls = await adapter.get_job_links()

        self.assertEqual(urls, ["https://mblabs.inhire.app/vagas/role-a"])
        page.locator.assert_called_once_with('a[href^="/vagas/"]')

    async def test_get_jobs_maps_titles_and_absolute_urls(self):
        page = MagicMock()
        links = MagicMock()
        links.count = AsyncMock(return_value=1)
        page.locator.return_value = links
        links.evaluate_all = AsyncMock(
            return_value=[
                {
                    "url": "https://mblabs.inhire.app/vagas/role-1/qa-engineer",
                    "title": "  QA   Engineer ",
                    "visible": True,
                }
            ]
        )
        page.evaluate = AsyncMock()
        page.evaluate.side_effect = [
            None,
            1442,
            None,
            1442,
            None,
            1442,
            None,
            1442,
        ]
        page.wait_for_timeout = AsyncMock()
        adapter = InHireAdapter(page)

        jobs = await adapter.get_jobs()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "QA Engineer")
        self.assertEqual(
            jobs[0].url,
            "https://mblabs.inhire.app/vagas/role-1/qa-engineer",
        )
        self.assertEqual(page.evaluate.await_count, 8)
        self.assertEqual(page.wait_for_timeout.await_count, 4)

    async def test_get_jobs_ignores_navigation_and_hidden_or_stale_links(self):
        page = MagicMock()
        links = MagicMock()
        page.locator.return_value = links
        links.evaluate_all = AsyncMock(
            return_value=[
                {
                    "url": "https://eqi.inhire.app/vagas",
                    "title": "Jobs",
                    "visible": True,
                },
                {
                    "url": "https://eqi.inhire.app/vagas/role-1/qa-engineer",
                    "title": "QA Engineer",
                    "visible": True,
                },
                {
                    "url": "https://eqi.inhire.app/vagas/role-2/developer",
                    "title": "Developer",
                    "visible": False,
                },
                {
                    "url": "https://eqi.inhire.app/vagas/role-3/test-analyst",
                    "title": "Test Analyst",
                    "visible": True,
                },
            ]
        )
        links.count = AsyncMock(return_value=4)
        page.evaluate = AsyncMock()
        page.evaluate.side_effect = [
            None,
            100,
            None,
            100,
            None,
            100,
            None,
            100,
        ]
        page.wait_for_timeout = AsyncMock()
        adapter = InHireAdapter(page)

        jobs = await adapter.get_jobs()

        self.assertEqual(
            [(job.title, job.url) for job in jobs],
            [
                (
                    "QA Engineer",
                    "https://eqi.inhire.app/vagas/role-1/qa-engineer",
                ),
                (
                    "Test Analyst",
                    "https://eqi.inhire.app/vagas/role-3/test-analyst",
                ),
            ],
        )
        links.evaluate_all.assert_awaited_once()

    async def test_get_jobs_warns_if_lazy_listing_never_stabilizes(self):
        page = MagicMock()
        links = MagicMock()
        links.count = AsyncMock(side_effect=range(1, 31))
        links.evaluate_all = AsyncMock(return_value=[])
        page.locator.return_value = links
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        adapter = InHireAdapter(page)

        with patch("agents.platforms.inhire.print") as print_mock:
            await adapter.get_jobs()

        print_mock.assert_called_once()
        self.assertIn("may be incomplete", print_mock.call_args.args[0])
        self.assertEqual(page.evaluate.await_count, 60)


@unittest.skipUnless(
    os.environ.get("RUN_INHIRE_LIVE_TEST") == "1",
    "Set RUN_INHIRE_LIVE_TEST=1 to exercise the live InHire page.",
)
class InHireLivePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_page_loads_jobs_without_using_search_input(self):
        from playwright.async_api import async_playwright

        keep_open = os.environ.get("INHIRE_KEEP_BROWSER_OPEN") == "1"
        headless = not keep_open and os.environ.get("INHIRE_HEADLESS") != "0"

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            try:
                page = await browser.new_page()
                await page.goto(
                    "https://mblabs.inhire.app/vagas",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                adapter = InHireAdapter(page)

                await adapter.wait_for_page_ready()
                jobs = await adapter.get_jobs()
                card_count = await page.locator(INHIRE_MODEL.job_cards[0]).count()
                print(
                    "InHire live mapping: "
                    + json.dumps(
                        {
                            "url": page.url,
                            "job_link_selector": INHIRE_MODEL.job_links[0],
                            "job_count": len(jobs),
                            "jobs": [
                                {"title": job.title, "url": job.url}
                                for job in jobs
                            ],
                            "job_card_selector": INHIRE_MODEL.job_cards[0],
                            "job_card_count": card_count,
                            "next_page_selectors": INHIRE_MODEL.next_page,
                        },
                        ensure_ascii=False,
                    )
                )

                self.assertGreater(len(jobs), 0, "No job links matched the configured selector")
                self.assertTrue(
                    all(
                        job.url.startswith("https://mblabs.inhire.app/vagas/")
                        for job in jobs
                    ),
                    "A mapped link did not point to an InHire job page",
                )

                if keep_open:
                    await asyncio.to_thread(
                        input,
                        "Live InHire page is open. Press Enter here to close the browser...",
                    )
            finally:
                await browser.close()


if __name__ == "__main__":
    unittest.main()
