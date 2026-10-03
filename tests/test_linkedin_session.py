import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer
from services.linkedin_session import LinkedInSession


class LinkedInSessionTests(unittest.TestCase):
    def test_login_detection_uses_me_menu_button(self):
        class Locator:
            def __init__(self, exists):
                self.exists = exists

            async def count(self):
                return int(self.exists)

        class FakePage:
            url = "https://www.linkedin.com/feed/"

            def locator(self, selector):
                return Locator(
                    selector
                    == "button.global-nav__primary-link-me-menu-trigger"
                )

        session = LinkedInSession()
        session.page = FakePage()

        self.assertTrue(asyncio.run(session.is_logged_in()))

    def test_login_check_can_be_retried_from_terminal(self):
        session = LinkedInSession()
        session.page = object()

        with (
            patch.object(
                session,
                "is_logged_in",
                new=AsyncMock(side_effect=[False, True]),
            ),
            patch(
                "services.linkedin_session.asyncio.to_thread",
                new=AsyncMock(return_value=""),
            ),
        ):
            self.assertTrue(asyncio.run(session.login_manually()))

    def test_login_check_can_be_skipped_or_aborted(self):
        session = LinkedInSession()
        session.page = object()

        with patch(
            "services.linkedin_session.asyncio.to_thread",
            new=AsyncMock(return_value="s"),
        ):
            self.assertTrue(asyncio.run(session.login_manually()))

        with patch(
            "services.linkedin_session.asyncio.to_thread",
            new=AsyncMock(return_value="q"),
        ):
            self.assertFalse(asyncio.run(session.login_manually()))


class MeuPadrinhoApplicationLinkTests(unittest.TestCase):
    def test_apply_button_returns_linkedin_url_without_visiting_it(self):
        linkedin_url = "https://www.linkedin.com/jobs/view/123/"

        class Locator:
            def __init__(self, href=""):
                self.href = href

            async def count(self):
                return int(bool(self.href))

            def nth(self, index):
                return self

            async def is_visible(self):
                return True

            async def get_attribute(self, name):
                return self.href

        class FakePage:
            def get_by_role(self, role, name, exact):
                href = linkedin_url if role == "link" else ""
                return Locator(href)

            def get_by_text(self, text, exact):
                return Locator()

        result = asyncio.run(
            MeuPadrinhoAnalyzer().get_apply_button(FakePage())
        )
        self.assertEqual(result, linkedin_url)