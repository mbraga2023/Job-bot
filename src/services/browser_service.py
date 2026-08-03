from playwright.async_api import async_playwright

from config import TIMEOUT


async def open_page(url: str, headless: bool = True):

    playwright = await async_playwright().start()

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