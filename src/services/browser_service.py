#browser_service.py
from playwright.async_api import async_playwright

from config import TIMEOUT


async def open_page(url: str, headless: bool = True, playwright=None, browser=None):
    if playwright is None:
        playwright = await async_playwright().start()

    if browser is None:
        browser = await playwright.chromium.launch(
            headless=headless
        )

    page = await browser.new_page()

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=TIMEOUT
    )

    return playwright, browser, page