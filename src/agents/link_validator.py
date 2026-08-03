## link_validator.py
from config import HEADLESS
from services.browser_service import open_page
from database.database import get_meupadrinho_jobs
from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer
from services.json_service import append_analysis

async def run():

    jobs = get_meupadrinho_jobs()

    if not jobs:
        print("No MeuPadrinho jobs found.")
        return

    print(f"Retrieved {len(jobs)} jobs from database.")

    analyzer = MeuPadrinhoAnalyzer()

    results = []

    total = len(jobs)


    for index, job_data in enumerate(jobs, start=1):

        url = job_data["link"]

        print(f"\n[{index}/{total}] Processing: {url}")

        playwright, browser, page = await open_page(
            url,
            headless=HEADLESS
        )

        try:

            job = await analyzer.analyze(page)

            job["source_data"] = {

                "id": job_data["id"],
                "original_title": job_data["title"],
                "original_company": job_data["company"],
                "score": job_data["score"],
                "link": job_data["link"],
                "created_at": job_data["created_at"]

            }

            results.append(job)

            output = append_analysis(job)


            if job["page_not_found"]:
                print("⚠ Page not found")
            else:
                print("✓ Analyzed")


            print(f"Saved: {output}")

        except Exception as error:

            print(f"✗ Failed: {error}")

        finally:

            await browser.close()
            await playwright.stop()


    output = None

    if results:
        output = "output/job_analysis.json"


    print("\n==============================")
    print("Validation finished")
    print(f"Jobs retrieved : {total}")
    print(f"Jobs analyzed  : {len(results)}")

    if output:
        print(f"Output         : {output}")

    print("==============================")