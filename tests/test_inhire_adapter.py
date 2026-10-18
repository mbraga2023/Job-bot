import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

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


@unittest.skipUnless(
    os.environ.get("RUN_INHIRE_LIVE_TEST") == "1",
    "Set RUN_INHIRE_LIVE_TEST=1 to exercise the live InHire page.",
)
class InHireLivePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_page_maps_search_and_job_links(self):
        from playwright.async_api import async_playwright, expect

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
                search_locator = page.locator(INHIRE_MODEL.search_input[0])
                await search_locator.wait_for(state="visible", timeout=15_000)
                await page.locator(INHIRE_MODEL.job_links[0]).first.wait_for(
                    state="visible",
                    timeout=15_000,
                )
                search_visible = await search_locator.is_visible()
                urls = await adapter.get_job_links()
                card_count = await page.locator(INHIRE_MODEL.job_cards[0]).count()
                print(
                    "InHire live mapping: "
                    + json.dumps(
                        {
                            "url": page.url,
                            "search_selector": INHIRE_MODEL.search_input[0],
                            "search_visible": search_visible,
                            "job_link_selector": INHIRE_MODEL.job_links[0],
                            "job_count": len(urls),
                            "job_urls": urls,
                            "job_card_selector": INHIRE_MODEL.job_cards[0],
                            "job_card_count": card_count,
                            "next_page_selectors": INHIRE_MODEL.next_page,
                        },
                        ensure_ascii=False,
                    )
                )

                self.assertTrue(search_visible, "Configured search field was not visible")
                self.assertGreater(len(urls), 0, "No job links matched the configured selector")
                self.assertTrue(
                    all(url.startswith("https://mblabs.inhire.app/vagas/") for url in urls),
                    "A mapped link did not point to an InHire job page",
                )

                self.assertTrue(await adapter.search("Quality Assurance"))
                await expect(page.locator(INHIRE_MODEL.job_links[0])).to_have_count(
                    1,
                    timeout=15_000,
                )
                filtered_urls = await adapter.get_job_links()
                print(
                    "InHire live search results: "
                    + json.dumps(filtered_urls, ensure_ascii=False)
                )
                self.assertTrue(
                    any("quality-assurance" in url for url in filtered_urls),
                    "Search submitted but no matching Quality Assurance job was mapped",
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
