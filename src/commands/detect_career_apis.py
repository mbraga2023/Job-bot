from playwright.async_api import async_playwright

from config import HEADLESS

from database.career_sources import (
    get_all_career_sources,
    update_career_source_status,
    mark_source_checked,
)

from agents.career_api_detector import (
    CareerApiDetector,
)


async def run():

    sources = get_all_career_sources()

    if not sources:

        print("No career sources found.")
        return

    print()
    print("=" * 60)
    print("STAGE 1.2 - CAREER API DETECTION")
    print("=" * 60)

    print(
        f"Career sources: {len(sources)}"
    )

    detector = CareerApiDetector()

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=HEADLESS
        )

        context = await browser.new_context()

        for index, source in enumerate(
            sources,
            start=1,
        ):

            source_id = source["id"]
            company = source["company"]
            url = source["careers_url"]

            print()
            print("-" * 60)

            print(
                f"[{index}/{len(sources)}] "
                f"{company}"
            )

            print(
                f"URL: {url}"
            )

            page = await context.new_page()

            try:

                # -------------------------------------------------
                # Detect API
                # -------------------------------------------------

                result = await detector.detect(
                    page,
                    url,
                )

                platform = result["platform"]
                responses = result["responses"]
                best_api = result["best_api"]

                print(
                    f"  Platform: {platform}"
                )

                # -------------------------------------------------
                # Show discovered APIs
                # -------------------------------------------------

                if responses:

                    print(
                        f"  Found {len(responses)} "
                        f"JSON API request(s)."
                    )

                else:

                    print(
                        "  → No JSON API requests detected."
                    )

                # -------------------------------------------------
                # No useful API
                # -------------------------------------------------

                if not best_api:

                    print(
                        "  → No useful job API candidate found."
                    )

                    update_career_source_status(
                        source_id=source_id,
                        source_type=platform,
                    )

                    mark_source_checked(
                        source_id=source_id,
                        success=True,
                    )

                    continue

                # -------------------------------------------------
                # Useful API found
                # -------------------------------------------------

                print()
                print(
                    "  ✓ JOB API CANDIDATE"
                )

                print(
                    f"    Score: "
                    f"{best_api['score']}"
                )

                print(
                    f"    Method: "
                    f"{best_api['method']}"
                )

                print(
                    f"    Status: "
                    f"{best_api['status']}"
                )

                print(
                    f"    URL: "
                    f"{best_api['url']}"
                )

                # -------------------------------------------------
                # Save API information
                # -------------------------------------------------

                api_config = {
                    "content_type": best_api[
                        "content_type"
                    ],
                    "detection_score": best_api[
                        "score"
                    ],
                }

                update_career_source_status(
                    source_id=source_id,
                    source_type=platform,
                    api_url=best_api["url"],
                    api_method=best_api["method"],
                    api_config=api_config,
                )

                mark_source_checked(
                    source_id=source_id,
                    success=True,
                )

                print()
                print(
                    "  ✓ Career source updated."
                )

            except Exception as error:

                print(
                    f"  ✗ Failed: {error}"
                )

                mark_source_checked(
                    source_id=source_id,
                    success=False,
                    error=str(error),
                )

            finally:

                await page.close()

        await context.close()
        await browser.close()

    print()
    print("=" * 60)
    print("Career API detection finished")
    print("=" * 60)


if __name__ == "__main__":

    import asyncio

    asyncio.run(run())