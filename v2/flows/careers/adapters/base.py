"""Base Career Page Crawler Adapter for v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from playwright.async_api import Page


@dataclass
class CareerJobItem:
    """Discovered career job listing."""
    title: str
    url: str
    company: str | None = None
    location: str | None = None
    external_id: str | None = None
    published_date: str | None = None
    raw_data: dict[str, Any] | None = None


@dataclass
class CareerPageModel:
    platform: str
    search_input: list[str] = field(default_factory=list)
    search_button: list[str] = field(default_factory=list)
    job_links: list[str] = field(default_factory=list)
    job_cards: list[str] = field(default_factory=list)
    next_page: list[str] = field(default_factory=list)


class BaseCareerAdapter:
    """Base class for platform-specific and generic career page adapters."""

    def __init__(self, page: Page, model: CareerPageModel):
        self.page = page
        self.model = model

    async def search(self, term: str) -> bool:
        """Search using the first available selector."""
        for selector in self.model.search_input:
            locator = self.page.locator(selector).first
            try:
                if await locator.is_visible(timeout=1500):
                    await locator.fill(term)
                    for button_selector in self.model.search_button:
                        btn = self.page.locator(button_selector).first
                        if await btn.is_visible(timeout=500):
                            await btn.click()
                            await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                            return True
                    await locator.press("Enter")
                    return True
            except Exception:
                continue
        return False

    async def get_job_links(self) -> list[str]:
        """Extract unique job URLs matching configured selectors."""
        urls: list[str] = []
        for selector in self.model.job_links:
            links = self.page.locator(selector)
            count = await links.count()
            for i in range(count):
                href = await links.nth(i).get_attribute("href")
                if href:
                    full_url = await links.nth(i).evaluate("(el) => el.href")
                    if full_url:
                        urls.append(full_url)
        return list(dict.fromkeys(urls))
