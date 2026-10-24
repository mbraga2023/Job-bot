"""Tests for batched job review flows."""

from __future__ import annotations

import unittest
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
            statuses=("OPEN", "VALIDATED"),
            limit=10,
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
            statuses=("VALIDATED",),
            limit=10,
        )
        self.assertEqual(len(mock_open.call_args.args[0]), 10)
        self.assertEqual(mock_update_status.call_count, 10)


if __name__ == "__main__":
    unittest.main()
