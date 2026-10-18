from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CareerPageModel:
    platform: str
    search_input: list[str] = field(default_factory=list)
    search_button: list[str] = field(default_factory=list)
    job_links: list[str] = field(default_factory=list)
    job_cards: list[str] = field(default_factory=list)
    next_page: list[str] = field(default_factory=list)


class BaseCareerAdapter:
    def __init__(self, page, model: CareerPageModel):
        self.page = page
        self.model = model

    async def search(self, term: str) -> bool:
        """Search using the first usable configured selector."""
        for selector in self.model.search_input:
            locator = self.page.locator(selector).first

            try:
                if await locator.is_visible(timeout=1500):
                    await locator.fill(term)

                    for button_selector in self.model.search_button:
                        button = self.page.locator(button_selector).first

                        if await button.is_visible(timeout=500):
                            await button.click()
                            await self.page.wait_for_load_state(
                                "domcontentloaded",
                                timeout=5000,
                            )
                            break
                    else:
                        # Some search inputs submit on Enter.
                        await locator.press("Enter")

                    return True

            except Exception:
                continue

        return False

    async def get_job_links(self) -> list[str]:
        """Return unique job URLs matching the configured selectors."""
        urls = []

        for selector in self.model.job_links:
            links = self.page.locator(selector)

            for i in range(await links.count()):
                href = await links.nth(i).get_attribute("href")

                if href:
                    urls.append(await links.nth(i).evaluate("(el) => el.href"))

        return list(dict.fromkeys(urls))
