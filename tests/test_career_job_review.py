import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("API_ID", "123")
os.environ.setdefault("API_HASH", "test-hash")
os.environ.setdefault("TELEGRAM_CHANNEL", "@example")

import config
import database.database as database_module
from commands.open_career_jobs import run as open_career_jobs
from database.career_job_details import (
    get_career_job_details,
    get_generic_job_links,
    get_new_career_job_details,
    insert_career_job_details,
)
from database.database import get_connection
from database.schema import create_database
from services.career_job_review import discard_ineligible_new_career_jobs


class CareerJobReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_database = config.DATABASE
        self.original_db_path = database_module.DB_PATH
        database_path = Path(self.tmpdir.name) / "career-jobs.db"
        config.DATABASE = database_path
        database_module.DB_PATH = database_path
        create_database()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO career_sources (company, careers_url)
                VALUES ('Test Company', 'https://example.com/careers')
                """
            )
            self.source_id = cursor.lastrowid
            conn.commit()
        self.next_id = 1

    def tearDown(self):
        config.DATABASE = self.original_database
        database_module.DB_PATH = self.original_db_path
        self.tmpdir.cleanup()

    def add_job(self, title, level, validated_at, status="NEW"):
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO career_jobs (career_source_id, title, company, url)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.source_id,
                    title,
                    "Test Company",
                    f"https://example.com/jobs/{self.next_id}",
                ),
            )
            career_job_id = cursor.lastrowid
            conn.commit()

        insert_career_job_details(
            career_job_id,
            f"https://example.com/jobs/{self.next_id}",
            {
                "title": title,
                "company": "Test Company",
                "level": level,
                "job_status": status,
            },
        )
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE career_job_details
                SET validated_at = ?
                WHERE career_job_id = ?
                """,
                (validated_at, career_job_id),
            )
            conn.commit()
        self.next_id += 1
        return career_job_id

    def get_status(self, career_job_id):
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT job_status
                FROM career_job_details
                WHERE career_job_id = ?
                """,
                (career_job_id,),
            ).fetchone()
        return row["job_status"]

    def test_generic_job_queue_can_return_all_pending_jobs(self):
        with get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO career_jobs (career_source_id, title, company, url)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        self.source_id,
                        f"QA Engineer {index}",
                        "Test Company",
                        f"https://example.com/jobs/{index}",
                    )
                    for index in range(3)
                ],
            )
            conn.commit()

        self.assertEqual(len(get_generic_job_links(limit=None)), 3)
        self.assertEqual(len(get_generic_job_links(limit=1)), 1)

    def test_published_date_is_saved_as_iso_date(self):
        career_job_id = self.add_job(
            "QA Engineer", "Mid", "2999-01-01 00:00:00"
        )

        insert_career_job_details(
            career_job_id,
            f"https://example.com/jobs/{self.next_id - 1}",
            {
                "title": "QA Engineer",
                "published_date": "June 29, 2026",
            },
        )

        details = get_career_job_details(career_job_id)
        self.assertEqual(details["published_date"], "2026-06-29")

    def test_discards_new_junior_and_jobs_validated_over_30_days_ago(self):
        junior_id = self.add_job(
            "Junior QA", "Júnior", "2026-10-16 00:00:00"
        )
        stale_id = self.add_job(
            "Mid QA", "Pleno", "2020-01-01 00:00:00"
        )
        current_id = self.add_job(
            "Current QA", "Pleno", "2999-01-01 00:00:00"
        )
        already_closed_id = self.add_job(
            "Closed QA", "Junior", "2020-01-01 00:00:00", status="CLOSED"
        )

        discarded = discard_ineligible_new_career_jobs()

        self.assertEqual(discarded, {"junior": 1, "stale": 1})
        self.assertEqual(self.get_status(junior_id), "DISCARDED")
        self.assertEqual(self.get_status(stale_id), "DISCARDED")
        self.assertEqual(self.get_status(current_id), "NEW")
        self.assertEqual(self.get_status(already_closed_id), "CLOSED")

    @patch(
        "commands.open_career_jobs.open_in_chrome",
        return_value=(True, "Opened 1 tab"),
    )
    def test_open_command_opens_only_eligible_new_career_pages(
        self,
        open_in_chrome_mock,
    ):
        junior_id = self.add_job(
            "Junior QA", "Junior", "2999-01-01 00:00:00"
        )
        eligible_id = self.add_job(
            "QA Engineer", "Pleno", "2999-01-01 00:00:00"
        )
        stale_id = self.add_job(
            "Old QA", "Pleno", "2020-01-01 00:00:00"
        )

        open_career_jobs()

        open_in_chrome_mock.assert_called_once_with(
            ["https://example.com/jobs/2"]
        )
        self.assertEqual(self.get_status(junior_id), "DISCARDED")
        self.assertEqual(self.get_status(stale_id), "DISCARDED")
        self.assertEqual(self.get_status(eligible_id), "MANUAL")
        self.assertEqual(
            [job["career_job_id"] for job in get_new_career_job_details()],
            [],
        )

    @patch(
        "commands.open_career_jobs.open_in_chrome",
        return_value=(False, "Chrome failed"),
    )
    def test_open_command_does_not_mark_jobs_when_browser_fails(
        self,
        open_in_chrome_mock,
    ):
        career_job_id = self.add_job(
            "QA Engineer", "Pleno", "2999-01-01 00:00:00"
        )

        open_career_jobs()

        self.assertEqual(self.get_status(career_job_id), "NEW")


if __name__ == "__main__":
    unittest.main()
