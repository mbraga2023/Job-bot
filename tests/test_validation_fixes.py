import os
import unittest
from pathlib import Path
import tempfile

os.environ.setdefault("API_ID", "123")
os.environ.setdefault("API_HASH", "test-hash")
os.environ.setdefault("TELEGRAM_CHANNEL", "@example")

from core import parser, scorer, classifier
from services import json_service


class ValidationFixesTests(unittest.TestCase):
    def test_parser_has_no_extract_link(self):
        self.assertFalse(hasattr(parser, "extract_link"))

    def test_is_remote_excludes_brasil_keyword(self):
        from services.telegram_service import is_remote

        self.assertFalse(is_remote({"title": "vaga no brasil"}))
        self.assertTrue(is_remote({"title": "vaga remota"}))

    def test_scores_are_capped_at_hundred(self):
        job = {"title": "QA automation senior remote java python playwright"}
        self.assertLessEqual(scorer.score_job(job), 100)

    def test_classifier_handles_missing_title(self):
        self.assertEqual(classifier.classify({}), "OTHER")

    def test_json_service_deduplicates_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_json = json_service.JSON_PATH
            json_service.JSON_PATH = Path(tmpdir) / "job_analysis.json"
            try:
                first = {"source_data": {"id": 7, "link": "https://example.com/a"}}
                second = {"source_data": {"id": 7, "link": "https://example.com/a"}}
                json_service.append_analysis(first)
                json_service.append_analysis(second)
                self.assertEqual(len(json_service.load_analysis()), 1)
            finally:
                json_service.JSON_PATH = original_json

    def test_job_details_schema_keys_are_compatible(self):
        import database.database as database_module
        from database.database import get_connection
        from database.job_details import insert_job_details

        details = {
            "page_not_found": False,
            "published_date": "2024-01-02",
            "title": "Python Developer",
            "company": "Acme",
            "location": "Remote",
            "remote": True,
            "level": "Senior",
            "contract": "CLT",
            "job_source": "meupadrinho",
            "application_url": "https://example.com/apply",
            "application_source": "meupadrinho",
            "description": "Build software",
            "technologies": ["Python"],
            "requirements": ["Testing"],
            "differentials": ["AWS"],
            "benefits": ["Health plan"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test.db"
            original_db_path = database_module.DB_PATH
            database_module.DB_PATH = temp_db
            try:
                import config

                config.DATABASE = temp_db
                from database import schema

                schema.create_database()
                job_id = 1
                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO jobs (id, telegram_hash, link) VALUES (?, ?, ?)",
                        (job_id, "hash-1", "https://example.com/job"),
                    )
                    conn.commit()
                row_id = insert_job_details(job_id, details)
                self.assertGreater(row_id, 0)
                saved = get_connection().execute(
                    "SELECT job_source, application_url, application_source FROM job_details WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                self.assertEqual(saved["job_source"], "meupadrinho")
                self.assertEqual(saved["application_url"], "https://example.com/apply")
                self.assertEqual(saved["application_source"], "meupadrinho")
            finally:
                database_module.DB_PATH = original_db_path


if __name__ == "__main__":
    unittest.main()
