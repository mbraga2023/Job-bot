import unittest
from unittest.mock import call, patch, MagicMock
import tempfile
from pathlib import Path

import config
import database.database as database_module
from database.database import get_connection
from database.schema import create_database
from database.job_details import insert_job_details, update_job_status, get_jobs_to_review
from services.browser_launcher import find_chrome_path, open_in_chrome
from commands.open_jobs import run as run_open_jobs


class OpenJobsTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_db = Path(self.tmpdir.name) / "test.db"
        self.original_db = config.DATABASE
        self.original_db_path = database_module.DB_PATH
        config.DATABASE = self.temp_db
        database_module.DB_PATH = self.temp_db
        create_database()

    def tearDown(self):
        config.DATABASE = self.original_db
        database_module.DB_PATH = self.original_db_path
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_get_jobs_to_review_filters_open_and_new_jobs(self):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO jobs (id, telegram_hash, link, title, company) VALUES (?, ?, ?, ?, ?)",
                (1, "h1", "https://example.com/job1", "QA Pleno", "Company A"),
            )
            conn.execute(
                "INSERT INTO jobs (id, telegram_hash, link, title, company) VALUES (?, ?, ?, ?, ?)",
                (2, "h2", "https://example.com/job2", "QA Senior", "Company B"),
            )
            conn.execute(
                "INSERT INTO jobs (id, telegram_hash, link, title, company) VALUES (?, ?, ?, ?, ?)",
                (3, "h3", "https://example.com/job3", "QA Engineer", "Company C"),
            )
            conn.execute(
                "INSERT INTO jobs (id, telegram_hash, link, title, company) VALUES (?, ?, ?, ?, ?)",
                (4, "h4", "https://example.com/job4", "QA Lead", "Company D"),
            )
            conn.commit()

        insert_job_details(1, {"title": "QA Pleno", "company": "Company A", "application_url": "https://apply.com/1"})
        update_job_status(1, "NEW")

        insert_job_details(2, {"title": "QA Senior", "company": "Company B", "application_url": "https://apply.com/2"})
        update_job_status(2, "CLOSED")

        insert_job_details(3, {"title": "QA Engineer", "company": "Company C", "application_url": "https://apply.com/3"})
        update_job_status(3, "OPEN")

        insert_job_details(4, {"title": "QA Lead", "company": "Company D", "application_url": "https://apply.com/4", "page_not_found": True})
        update_job_status(4, "NEW")

        # Only job 3 (OPEN) and job 1 (NEW, page_not_found=0) should be returned
        jobs = get_jobs_to_review()
        self.assertEqual(len(jobs), 2)
        # OPEN job should be prioritized first
        self.assertEqual(jobs[0]["job_status"], "OPEN")
        self.assertEqual(jobs[0]["job_id"], 3)
        self.assertEqual(jobs[1]["job_status"], "NEW")
        self.assertEqual(jobs[1]["job_id"], 1)

    def test_manual_is_a_persistable_job_status(self):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO jobs (id, telegram_hash, link, title, company) VALUES (?, ?, ?, ?, ?)",
                (5, "h5", "https://example.com/job5", "QA Manual", "Company E"),
            )
            conn.commit()

        insert_job_details(
            5,
            {
                "title": "QA Manual",
                "company": "Company E",
                "application_url": "https://apply.com/5",
            },
        )
        update_job_status(5, "MANUAL")

        with get_connection() as conn:
            status = conn.execute(
                "SELECT job_status FROM job_details WHERE job_id = ?",
                (5,),
            ).fetchone()["job_status"]

        self.assertEqual(status, "MANUAL")

    def test_find_chrome_path_returns_string(self):
        path = find_chrome_path()
        # On this Windows machine, Chrome is installed
        self.assertIsNotNone(path)
        self.assertTrue(Path(path).is_file())

    @patch("services.browser_launcher.subprocess.Popen")
    def test_open_in_chrome_invokes_popen_with_new_window(self, mock_popen):
        urls = ["https://example.com/1", "https://example.com/2"]
        success, msg = open_in_chrome(urls)
        self.assertTrue(success)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertEqual(args[1], "--new-window")
        self.assertIn("https://example.com/1", args)
        self.assertIn("https://example.com/2", args)

    @patch("commands.open_jobs.open_in_chrome")
    def test_command_run_handles_empty_jobs(self, mock_open):
        run_open_jobs()
        mock_open.assert_not_called()

    @patch("commands.open_jobs.update_job_status")
    @patch(
        "commands.open_jobs.open_in_chrome",
        return_value=(True, "Opened 2 tabs"),
    )
    @patch(
        "commands.open_jobs.get_jobs_to_review",
        return_value=[
            {
                "job_id": 101,
                "title": "QA Engineer",
                "company": "Company A",
                "job_status": "OPEN",
                "target_url": "https://example.com/job/101",
            },
            {
                "job_id": 102,
                "title": "QA Analyst",
                "company": "Company B",
                "job_status": "NEW",
                "target_url": "https://example.com/job/102",
            },
        ],
    )
    def test_command_marks_opened_open_and_new_jobs_as_manual(
        self,
        mock_get_jobs,
        mock_open,
        mock_update_status,
    ):
        run_open_jobs()

        mock_get_jobs.assert_called_once_with(
            statuses=("OPEN", "NEW"),
            limit=None,
        )
        mock_open.assert_called_once_with(
            [
                "https://example.com/job/101",
                "https://example.com/job/102",
            ],
        )
        self.assertEqual(
            mock_update_status.call_args_list,
            [
                call(101, "MANUAL"),
                call(102, "MANUAL"),
            ],
        )

    @patch("commands.open_jobs.update_job_status")
    @patch(
        "commands.open_jobs.open_in_chrome",
        return_value=(False, "Chrome failed"),
    )
    @patch(
        "commands.open_jobs.get_jobs_to_review",
        return_value=[
            {
                "job_id": 101,
                "title": "QA Engineer",
                "company": "Company A",
                "job_status": "OPEN",
                "target_url": "https://example.com/job/101",
            },
        ],
    )
    def test_command_does_not_mark_jobs_if_chrome_fails(
        self,
        mock_get_jobs,
        mock_open,
        mock_update_status,
    ):
        run_open_jobs()

        mock_update_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
