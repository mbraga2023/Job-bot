from config import HEADLESS

from services.browser_service import open_page
from services.excel_service import read_jobs

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer


async def run():

    df = read_jobs()

    if df.empty:
        return

    url = df.iloc[0]["Link"]

    playwright, browser, page = await open_page(
        url,
        headless=HEADLESS
    )

    try:

        if "meupadrinho" in url.lower():

            analyzer = MeuPadrinhoAnalyzer()

            job = await analyzer.analyze(page)

            print(job)

    finally:

        await browser.close()

        await playwright.stop()