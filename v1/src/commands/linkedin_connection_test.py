import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False,
        )

        page = await browser.new_page()

        try:
            print("Opening LinkedIn...")

            response = await page.goto(
                "https://www.linkedin.com/",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            print("STATUS:", response.status if response else None)
            print("URL:", page.url)
            print("TITLE:", await page.title())

        except Exception as exc:
            print()
            print("=" * 70)
            print("LINKEDIN CONNECTION ERROR")
            print("=" * 70)
            print(type(exc).__name__)
            print(str(exc))
            print("=" * 70)

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())