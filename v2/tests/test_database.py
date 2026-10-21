"""Unit Tests for Centralized Database Schema and Repository."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v2.config import config
from v2.core.database import (
    get_connection,
    get_database_stats,
    get_job_by_id,
    get_job_by_source_url,
    get_jobs_for_review,
    get_jobs_for_validation,
    init_db,
    insert_career_source,
    insert_discovered_job,
    update_job_status,
    update_job_validation,
)


class TestCentralizedDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_jobs.db"
        # Temporarily redirect config.db_path
        self._orig_db_path = config.db_path
        config.db_path = self.db_path
        init_db(self.db_path)

    def tearDown(self):
        config.db_path = self._orig_db_path
        self.temp_dir.cleanup()

    def test_schema_creation(self):
        with get_connection(self.db_path) as conn:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
        self.assertIn("career_sources", tables)
        self.assertIn("jobs", tables)

    def test_insert_career_source(self):
        row_id = insert_career_source("TestCorp", "https://test.com/careers")
        self.assertGreater(row_id, 0)
        # Unique constraint test
        dup_id = insert_career_source("TestCorp", "https://test.com/careers")
        self.assertEqual(dup_id, 0)

    def test_telegram_and_career_jobs_lifecycle(self):
        # 1. Insert Telegram job
        tg_id = insert_discovered_job(
            pipeline="TELEGRAM",
            source_url="https://meupadrinho.com/job/1",
            title="QA Analyst",
            company="Startup A",
            remote=1,
            level="Pleno",
        )
        self.assertIsNotNone(tg_id)

        # 2. Insert Career job
        src_id = insert_career_source("TechCo", "https://techco.com/careers")
        cj_id = insert_discovered_job(
            pipeline="CAREER_PAGE",
            source_url="https://techco.com/jobs/42",
            title="Software Test Engineer",
            company="TechCo",
            career_source_id=src_id,
        )
        self.assertIsNotNone(cj_id)

        # Verify initial DISCOVERED status
        job = get_job_by_id(tg_id)
        self.assertEqual(job["status"], "DISCOVERED")
        self.assertEqual(job["pipeline"], "TELEGRAM")

        # Validation stage
        update_job_validation(
            job_id=tg_id,
            status="VALIDATED",
            description="Great testing job",
            technologies=["Playwright", "Python"],
            published_date="2026-10-18",
        )
        job = get_job_by_id(tg_id)
        self.assertEqual(job["status"], "VALIDATED")
        self.assertIn("Playwright", job["technologies"])

        # Review stage: open in Chrome -> MANUAL
        review_jobs = get_jobs_for_review(pipeline="TELEGRAM", statuses=("VALIDATED",))
        self.assertEqual(len(review_jobs), 1)
        self.assertEqual(review_jobs[0]["id"], tg_id)

        update_job_status(tg_id, "MANUAL")
        job = get_job_by_id(tg_id)
        self.assertEqual(job["status"], "MANUAL")

    def test_database_stats(self):
        insert_career_source("Co A", "https://coa.com")
        insert_career_source("Co B", "https://cob.com")
        insert_discovered_job(pipeline="TELEGRAM", source_url="https://tg.com/1")
        insert_discovered_job(pipeline="CAREER_PAGE", source_url="https://cp.com/1")

        stats = get_database_stats()
        self.assertEqual(stats["career_sources_total"], 2)
        self.assertEqual(stats["jobs_total"], 2)
        self.assertEqual(stats["jobs_by_pipeline"]["TELEGRAM"], 1)
        self.assertEqual(stats["jobs_by_pipeline"]["CAREER_PAGE"], 1)


if __name__ == "__main__":
    unittest.main()
