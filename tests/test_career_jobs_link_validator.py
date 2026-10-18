import unittest

from agents.career_jobs_link_validator import (
    get_job_status,
    get_validation_status,
)


class CareerJobsLinkValidatorStatusTests(unittest.TestCase):
    def test_job_status_prioritizes_page_not_found_and_discarded(self):
        self.assertEqual(
            get_job_status(
                {
                    "page_not_found": True,
                    "title": "Junior QA Engineer",
                    "level": "Junior",
                }
            ),
            "CLOSED",
        )
        self.assertEqual(
            get_job_status({"level": "Junior"}),
            "DISCARDED",
        )

    def test_job_status_preserves_closed_and_flags_missing_extraction(self):
        self.assertEqual(
            get_job_status({"job_status": "CLOSED", "title": "QA Engineer"}),
            "CLOSED",
        )
        self.assertEqual(
            get_job_status({}),
            "EXTRACTION_FAILED",
        )
        self.assertEqual(
            get_job_status({"description": "QA position details"}),
            "NEW",
        )

    def test_page_not_found_status_takes_precedence(self):
        self.assertEqual(
            get_validation_status(
                {
                    "page_not_found": True,
                    "job_status": "CLOSED",
                    "title": "Software Engineer",
                }
            ),
            "PAGE_NOT_FOUND",
        )

    def test_closed_and_discarded_jobs_have_distinct_statuses(self):
        self.assertEqual(
            get_validation_status({"job_status": "CLOSED"}),
            "JOB_CLOSED",
        )
        self.assertEqual(
            get_validation_status({"job_status": "DISCARDED"}),
            "JOB_DISCARDED",
        )

    def test_extracted_job_and_empty_result_have_distinct_statuses(self):
        self.assertEqual(
            get_validation_status(
                {"job_status": "NEW", "title": "Software Engineer"}
            ),
            "JOBS_FOUND",
        )
        self.assertEqual(
            get_validation_status({"job_status": "NEW"}),
            "NO_JOBS_FOUND",
        )

    def test_extraction_failed_status_is_reported(self):
        self.assertEqual(
            get_validation_status({"job_status": "EXTRACTION_FAILED"}),
            "EXTRACTION_FAILED",
        )


if __name__ == "__main__":
    unittest.main()
