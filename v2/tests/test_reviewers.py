"""Tests for batched job review flows."""

from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from v2.flows.careers.reviewer import run as run_career_review
from v2.flows.telegram.reviewer import run as run_telegram_review


class TestReviewBatches(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = [
            {
                "id": job_id,
                "title": f"QA Engineer {job_id}",
                "company": "Example",
                "status": "VALIDATED",
                "remote": 0 if job_id == 1 else 1,
                "application_url": f"https://example.com/jobs/{job_id}",
                "source_url": f"https://example.com/source/{job_id}",
            }
            for job_id in range(1, 13)
        ]

    @patch("v2.flows.telegram.reviewer.update_job_status")
    @patch("v2.flows.telegram.reviewer.open_urls_in_chrome", return_value=(True, "Opened 10 tabs"))
    @patch("v2.flows.telegram.reviewer.get_jobs_for_review")
    def test_telegram_review_caps_batch_at_ten(
        self,
        mock_get_jobs,
        mock_open,
        mock_update_status,
    ) -> None:
        mock_get_jobs.return_value = self.jobs

        run_telegram_review(limit=100)

        mock_get_jobs.assert_called_once_with(
            pipeline="TELEGRAM",
            statuses=("OPEN", "VALIDATED", "EASY_APPLY"),
            limit=10,
            remote_only=False,
        )
        self.assertEqual(len(mock_open.call_args.args[0]), 10)
        self.assertEqual(mock_update_status.call_count, 10)

    @patch("v2.flows.careers.reviewer.update_job_status")
    @patch("v2.flows.careers.reviewer.open_urls_in_chrome", return_value=(True, "Opened 10 tabs"))
    @patch("v2.flows.careers.reviewer.get_jobs_for_review")
    def test_career_review_caps_batch_at_ten(
        self,
        mock_get_jobs,
        mock_open,
        mock_update_status,
    ) -> None:
        mock_get_jobs.return_value = self.jobs

        run_career_review()

        mock_get_jobs.assert_called_once_with(
            pipeline="CAREER_PAGE",
            statuses=("OPEN", "VALIDATED"),
            limit=10,
        )
        self.assertEqual(len(mock_open.call_args.args[0]), 10)
        self.assertEqual(mock_update_status.call_count, 10)

    def test_career_review_skips_browser_when_no_jobs_or_urls_are_available(self) -> None:
        with (
            patch("v2.flows.careers.reviewer.get_jobs_for_review", return_value=[]),
            patch("v2.flows.careers.reviewer.open_urls_in_chrome") as open_urls,
            patch("v2.flows.careers.reviewer.update_job_status") as update_status,
            redirect_stdout(StringIO()),
        ):
            run_career_review(limit=0)
            open_urls.assert_not_called()
            update_status.assert_not_called()

        with (
            patch(
                "v2.flows.careers.reviewer.get_jobs_for_review",
                return_value=[{"id": 13, "title": "QA Engineer"}],
            ),
            patch("v2.flows.careers.reviewer.open_urls_in_chrome") as open_urls,
            patch("v2.flows.careers.reviewer.update_job_status") as update_status,
            redirect_stdout(StringIO()),
        ):
            run_career_review(limit=1)

        open_urls.assert_not_called()
        update_status.assert_not_called()

    def test_career_review_uses_fallback_url_and_leaves_jobs_unchanged_on_failure(self) -> None:
        jobs = [
            {"id": 14, "title": "QA Engineer"},
            {
                "id": 15,
                "title": "  QA &amp; Automation  ",
                "company": "A &amp; B",
                "status": None,
                "application_url": "",
                "source_url": "https://example.com/source/15",
            },
        ]
        output = StringIO()
        with (
            patch("v2.flows.careers.reviewer.get_jobs_for_review", return_value=jobs),
            patch(
                "v2.flows.careers.reviewer.open_urls_in_chrome",
                return_value=(False, "Browser unavailable"),
            ) as open_urls,
            patch("v2.flows.careers.reviewer.update_job_status") as update_status,
            redirect_stdout(output),
        ):
            run_career_review(limit=2)

        open_urls.assert_called_once_with(["https://example.com/source/15"])
        self.assertIn("A & B - QA & Automation", output.getvalue())
        self.assertIn("[NEW ]", output.getvalue())
        update_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
