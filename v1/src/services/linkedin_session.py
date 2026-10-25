from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
)


class LinkedInSession:
    """
    Persistent LinkedIn browser session.

    First run:
        - Opens LinkedIn
        - User logs in manually
        - Browser profile is persisted locally

    Future runs:
        - Reuses the same browser profile
        - Does not automate credential entry
        - Does not extract authentication cookies/tokens
    """

    LINKEDIN_URL = "https://www.linkedin.com/"
    PROFILE_DIR = Path("storage/linkedin_profile")

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self) -> Page:
        self.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.playwright = await async_playwright().start()

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.PROFILE_DIR),
            channel="chrome",
            headless=False,
            viewport={"width": 1440, "height": 900},
            chromium_sandbox=True,
        )


        self.page = (
            self.context.pages[0]
            if self.context.pages
            else await self.context.new_page()
        )

        await self.page.goto(
            self.LINKEDIN_URL,
            wait_until="domcontentloaded",
        )

        return self.page


    # =====================================================
    # Check login state
    # =====================================================

    async def is_logged_in(self) -> bool:

        if not self.page:
            raise RuntimeError(
                "Session has not been started."
            )

        url = self.page.url.lower()

        # Login/auth pages generally indicate
        # that the existing browser session isn't active.

        if "/login" in url:
            return False

        if "/checkpoint/" in url:
            return False

        if "/authwall" in url:
            return False

        # Check for common logged-in UI elements.

        selectors = [
            'a[href*="/in/"]',
            '[data-testid="nav-profile"]',
            'button[aria-label*="Me"]',
            'button.global-nav__primary-link-me-menu-trigger',
            'img[alt*="Photo"]',
        ]

        for selector in selectors:

            try:

                count = await self.page.locator(
                    selector
                ).count()

                if count > 0:
                    return True

            except Exception:
                continue

        return False

    # =====================================================
    # Manual login
    # =====================================================

    async def login_manually(self) -> bool:

        if not self.page:
            raise RuntimeError("Session has not been started.")

        print()
        print("=" * 70)
        print("LINKEDIN LOGIN CHECK")
        print("=" * 70)
        print("LinkedIn login could not be confirmed automatically.")
        print("Check the open Chrome window before choosing an option.")

        while True:
            try:
                answer = await asyncio.to_thread(
                    input,
                    "Press Enter to retry, type 's' to skip verification, "
                    "or 'q' to abort: ",
                )
            except (EOFError, OSError):
                print("No terminal input is available; stopping LinkedIn session.")
                return False

            choice = answer.strip().casefold()

            if choice in {"s", "skip"}:
                print("Skipping LinkedIn login verification for this run.")
                return True

            if choice in {"q", "quit", "abort"}:
                print("LinkedIn login check aborted.")
                return False

            if choice not in {"", "r", "retry"}:
                print("Choose Enter to retry, 's' to skip, or 'q' to abort.")
                continue

            if await self.is_logged_in():
                print()
                print("✓ LinkedIn session detected.")
                print(f"✓ Persistent profile: {self.PROFILE_DIR}")
                print()
                return True

            print("LinkedIn login is still not detected.")

    # =====================================================
    # Ensure authenticated
    # =====================================================

    async def ensure_authenticated(self) -> bool:

        if not self.page:
            await self.start()

        if await self.is_logged_in():

            print(
                "✓ Existing LinkedIn session is active."
            )

            return True

        print(
            "No active LinkedIn session found."
        )

        return await self.login_manually()

    # =====================================================
    # Get page
    # =====================================================

    async def get_page(self) -> Page:

        if not self.page:
            await self.start()

        if not await self.ensure_authenticated():
            raise RuntimeError("LinkedIn login was not confirmed.")

        return self.page

    # =====================================================
    # Close
    # =====================================================

    async def close(self):

        if self.context:

            await self.context.close()

            self.context = None

        if self.playwright:

            await self.playwright.stop()

            self.playwright = None

        self.page = None


# =========================================================
# Example
# =========================================================

async def main():

    session = LinkedInSession(
        headless=False
    )

    try:

        await session.start()

        authenticated = (
            await session.ensure_authenticated()
        )

        if not authenticated:

            print(
                "✗ LinkedIn authentication failed."
            )

            return

        print(
            "✓ Session ready."
        )

        page = await session.get_page()

        print(
            f"Current URL: {page.url}"
        )

        print(
            "Browser session is being preserved "
            "in the persistent profile."
        )

        # Keep browser open while testing.

        await page.wait_for_timeout(
            10000
        )

    finally:

        await session.close()


if __name__ == "__main__":

    asyncio.run(main())