from config import HEADLESS

from services.browser_service import open_page

from database.database import get_meupadrinho_jobs

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer


async def run():

    jobs = get_meupadrinho_jobs()

    if not jobs:
        return


    analyzer = MeuPadrinhoAnalyzer()


    for job_data in jobs:

        url = job_data["link"]

        print("\n================================")
        print(f"Processing: {url}")
        print("================================")


        playwright, browser, page = await open_page(
            url,
            headless=HEADLESS
        )

        try:

            job = await analyzer.analyze(page)

            print(job)


        except Exception as error:

            print(
                f"Error processing {url}: {error}"
            )


        finally:

            await browser.close()

            await playwright.stop()