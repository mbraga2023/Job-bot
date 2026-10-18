import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("API_ID", "123")
os.environ.setdefault("API_HASH", "test-hash")
os.environ.setdefault("TELEGRAM_CHANNEL", "@example")

from agents.career_jobs_link_validator import run
from services.career_job_title_classifier import classify_career_job_title


class CareerJobTitleClassifierTests(unittest.IsolatedAsyncioTestCase):
    @patch("services.career_job_title_classifier.ollama.AsyncClient")
    async def test_parses_llama_title_decision(self, client_mock):
        client = client_mock.return_value
        client.chat = AsyncMock()
        client.chat.return_value.message.content = (
            '{"is_qa_mid_level": false, "reason": "Senior role"}'
        )

        decision = await classify_career_job_title("Senior QA Engineer")

        self.assertEqual(
            decision,
            {"is_qa_mid_level": False, "reason": "Senior role"},
        )
        client.chat.assert_awaited_once()

    @patch("services.career_job_title_classifier.ollama.AsyncClient")
    async def test_rejects_invalid_llama_response(self, client_mock):
        client = client_mock.return_value
        client.chat = AsyncMock()
        client.chat.return_value.message.content = (
            '{"is_qa_mid_level": "no", "reason": "Senior role"}'
        )

        with self.assertRaisesRegex(ValueError, "boolean"):
            await classify_career_job_title("Senior QA Engineer")


class CareerJobValidatorAiTests(unittest.IsolatedAsyncioTestCase):
    def make_browser_mocks(self):
        playwright = MagicMock()
        browser = MagicMock()
        browser.close = AsyncMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)
        playwright.stop = AsyncMock()

        factory = MagicMock()
        factory.return_value.start = AsyncMock(return_value=playwright)
        return factory, playwright, browser

    @patch(
        "agents.career_jobs_link_validator.discard_ineligible_new_career_jobs",
        return_value={"junior": 0, "stale": 0},
    )
    @patch(
        "agents.career_jobs_link_validator.get_generic_job_links",
        return_value=[
            {
                "id": 42,
                "title": "QA Lead Auditor",
                "company": "Test Company",
                "location": "Remote",
                "url": "https://example.com/jobs/qa-lead-auditor",
            },
            {
                "id": 44,
                "title": "Senior QA Engineer",
                "company": "Test Company",
                "location": "Remote",
                "url": "https://example.com/jobs/senior-qa-engineer",
            },
        ],
    )
    @patch(
        "agents.career_jobs_link_validator.classify_career_job_title",
        new_callable=AsyncMock,
        side_effect=[
            {
                "is_qa_mid_level": False,
                "reason": "Lead role is above mid-level.",
            },
            {
                "is_qa_mid_level": False,
                "reason": "Senior role is above mid-level.",
            },
        ],
    )
    @patch("agents.career_jobs_link_validator.insert_career_job_details")
    @patch("agents.career_jobs_link_validator.append_analysis")
    @patch("agents.career_jobs_link_validator.open_page", new_callable=AsyncMock)
    @patch("agents.career_jobs_link_validator.async_playwright")
    async def test_rejected_title_logs_reason_without_opening_job_page(
        self,
        playwright_factory_mock,
        open_page_mock,
        append_mock,
        insert_mock,
        classify_mock,
        get_jobs_mock,
        discard_existing_mock,
    ):
        factory, _, _ = self.make_browser_mocks()
        playwright_factory_mock.side_effect = factory
        output = StringIO()

        with redirect_stdout(output):
            await run()

        get_jobs_mock.assert_called_once_with(limit=None)
        self.assertEqual(classify_mock.await_count, 2)
        self.assertEqual(
            [call.args[0] for call in classify_mock.await_args_list],
            ["QA Lead Auditor", "Senior QA Engineer"],
        )
        open_page_mock.assert_not_awaited()
        playwright_factory_mock.assert_not_called()
        self.assertEqual(insert_mock.call_count, 2)
        for call in insert_mock.call_args_list:
            details = call.kwargs["details"]
            self.assertEqual(details["job_status"], "DISCARDED")
            self.assertEqual(details["ai_status"], "COMPLETED")
        self.assertIn("Lead role is above mid-level.", output.getvalue())
        self.assertIn("Senior role is above mid-level.", output.getvalue())
        self.assertEqual(append_mock.call_count, 2)

    @patch(
        "agents.career_jobs_link_validator.discard_ineligible_new_career_jobs",
        return_value={"junior": 0, "stale": 0},
    )
    @patch(
        "agents.career_jobs_link_validator.get_generic_job_links",
        return_value=[
            {
                "id": 43,
                "title": "QA Engineer",
                "company": "Test Company",
                "location": "Remote",
                "url": "https://example.com/jobs/qa-engineer",
            }
        ],
    )
    @patch(
        "agents.career_jobs_link_validator.classify_career_job_title",
        new_callable=AsyncMock,
        return_value={"is_qa_mid_level": True, "reason": "Mid-level QA title."},
    )
    @patch("agents.career_jobs_link_validator.CareerJobsLinksAnalyzer")
    @patch("agents.career_jobs_link_validator.insert_career_job_details")
    @patch("agents.career_jobs_link_validator.update_career_job_status")
    @patch("agents.career_jobs_link_validator.append_analysis")
    @patch("agents.career_jobs_link_validator.open_page", new_callable=AsyncMock)
    @patch("agents.career_jobs_link_validator.async_playwright")
    async def test_accepted_title_is_scraped_and_extracted_discard_reason_is_logged(
        self,
        playwright_factory_mock,
        open_page_mock,
        append_mock,
        update_status_mock,
        insert_mock,
        analyzer_class_mock,
        classify_mock,
        get_jobs_mock,
        discard_existing_mock,
    ):
        factory, playwright, browser = self.make_browser_mocks()
        playwright_factory_mock.side_effect = factory
        page = MagicMock()
        page.url = "https://example.com/jobs/qa-engineer"
        page.title = AsyncMock(return_value="QA Engineer")
        page.close = AsyncMock()
        open_page_mock.return_value = (playwright, browser, page)
        details = {
            "page_not_found": False,
            "title": "QA Engineer",
            "company": "Test Company",
            "location": "Remote",
            "level": "Senior",
            "description": "Senior testing role.",
        }
        analyzer_class_mock.return_value.analyze = AsyncMock(
            return_value=details
        )
        output = StringIO()

        with redirect_stdout(output):
            await run()

        open_page_mock.assert_awaited_once()
        analyzer_class_mock.return_value.analyze.assert_awaited_once_with(
            page,
            fallback={
                "title": "QA Engineer",
                "company": "Test Company",
                "location": "Remote",
            },
        )
        saved_details = insert_mock.call_args.kwargs["details"]
        self.assertEqual(saved_details["job_status"], "DISCARDED")
        self.assertEqual(saved_details["ai_status"], "COMPLETED")
        self.assertIn("detected non-mid-level seniority: Senior", output.getvalue())
        update_status_mock.assert_called_once_with(43, "DISCARDED")
        append_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
