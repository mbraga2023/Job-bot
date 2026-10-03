import asyncio
import unittest
from unittest.mock import AsyncMock

from agents.analyzers.linkedin import LinkedInAnalyzer
from core.job_status import JOB_STATUS


class LinkedInAnalyzerTests(unittest.TestCase):
    def test_easy_apply_detector_scopes_to_job_details_header(self):
        class Button:
            async def is_visible(self):
                return True

        class Buttons:
            async def count(self):
                return 1

            def nth(self, index):
                return Button()

        class Section:
            def get_by_role(self, role, name):
                if role != "button" or not name.search("Easy Apply"):
                    return ButtonsEmpty()
                return Buttons()

        class ButtonsEmpty:
            async def count(self):
                return 0

        class Sections:
            def __init__(self, count):
                self.section_count = count

            async def count(self):
                return self.section_count

            def nth(self, index):
                return Section()

        class FakePage:
            def locator(self, selector):
                count = int(
                    selector
                    == ".job-details-jobs-unified-top-card__container--two-pane"
                )
                return Sections(count)

        result = asyncio.run(
            LinkedInAnalyzer()._has_easy_apply(FakePage())
        )

        self.assertTrue(result)

    def test_remote_easy_apply_job_gets_custom_status(self):
        class Body:
            async def inner_text(self, timeout):
                return "Remote"

        class FakePage:
            url = "https://www.linkedin.com/jobs/view/123/"

            async def wait_for_load_state(self, state, timeout):
                pass

            async def wait_for_selector(self, selector, timeout):
                pass

            async def wait_for_timeout(self, timeout):
                pass

            def locator(self, selector):
                return Body()

        analyzer = LinkedInAnalyzer()
        analyzer._detect_workplace = AsyncMock(return_value="REMOTE")
        analyzer._has_easy_apply = AsyncMock(return_value=True)

        result = asyncio.run(analyzer.analyze(FakePage()))

        self.assertEqual(result["job_status"], "linkedin_EasyApply")
        self.assertIn(result["job_status"], JOB_STATUS)

    def test_remote_job_without_easy_apply_stays_open(self):
        class Body:
            async def inner_text(self, timeout):
                return "Remote"

        class FakePage:
            url = "https://www.linkedin.com/jobs/view/123/"

            async def wait_for_load_state(self, state, timeout):
                pass

            async def wait_for_selector(self, selector, timeout):
                pass

            async def wait_for_timeout(self, timeout):
                pass

            def locator(self, selector):
                return Body()

        analyzer = LinkedInAnalyzer()
        analyzer._detect_workplace = AsyncMock(return_value="REMOTE")
        analyzer._has_easy_apply = AsyncMock(return_value=False)

        result = asyncio.run(analyzer.analyze(FakePage()))

        self.assertEqual(result["job_status"], "OPEN")