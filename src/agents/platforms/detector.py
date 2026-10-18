from urllib.parse import urlparse


async def detect_platform(page) -> str:
    hostname = urlparse(page.url).hostname or ""
    hostname = hostname.lower()

    # URL-based hints.
    if "inhire" in hostname:
        return "inhire"

    if "gupy" in hostname:
        return "gupy"

    # DOM-based fallback for custom domains.
    if await page.locator('[data-component-name="Input"]#name').count():
        return "inhire"

    # Add verified Gupy-specific DOM fingerprints here.
    return "generic"
