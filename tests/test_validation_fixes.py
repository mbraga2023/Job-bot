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

    def test_telegram_validation_discards_junior_estagio_and_senior(self):
        from agents.link_validator import should_discard

        self.assertTrue(should_discard({"level": "Junior"}))
        self.assertTrue(should_discard({"level": "Júnior"}))
        self.assertTrue(should_discard({"level": "Estágio"}))
        self.assertTrue(should_discard({"level": "Estagiário"}))
        self.assertTrue(should_discard({"level": "Senior"}))
        self.assertTrue(should_discard({"level": "Sênior"}))

        self.assertFalse(should_discard({"level": "Pleno"}))
        self.assertFalse(should_discard({"level": "Mid-level"}))
        self.assertFalse(should_discard({"level": "pleno"}))

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

    def test_linkedin_flow_can_replace_job_link_without_overwriting_duplicates(self):
        import database.database as database_module
        from database.database import get_connection
        from database.jobs import update_job_link

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test.db"
            original_db_path = database_module.DB_PATH
            database_module.DB_PATH = temp_db
            try:
                import config

                config.DATABASE = temp_db

                linkedin_url = "https://www.linkedin.com/jobs/view/123/"
                conn = get_connection()
                try:
                    conn.execute(
                        "CREATE TABLE jobs (id INTEGER PRIMARY KEY, link TEXT NOT NULL UNIQUE)"
                    )
                    conn.execute(
                        "INSERT INTO jobs (id, link) VALUES (?, ?)",
                        (1, "https://meupadrinho.com/jobs/1"),
                    )
                    conn.execute(
                        "INSERT INTO jobs (id, link) VALUES (?, ?)",
                        (2, linkedin_url),
                    )
                    conn.commit()
                finally:
                    conn.close()

                self.assertFalse(update_job_link(1, linkedin_url))
                self.assertTrue(
                    update_job_link(
                        1,
                        "https://www.linkedin.com/jobs/view/456/",
                    )
                )

                conn = get_connection()
                try:
                    link = conn.execute(
                        "SELECT link FROM jobs WHERE id = ?",
                        (1,),
                    ).fetchone()["link"]
                finally:
                    conn.close()

                self.assertEqual(
                    link,
                    "https://www.linkedin.com/jobs/view/456/",
                )
            finally:
                database_module.DB_PATH = original_db_path

    def test_career_job_details_upsert_on_duplicate_url(self):
        import database.database as database_module
        from database.database import get_connection
        from database import schema
        from database.career_job_details import insert_career_job_details

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test.db"
            original_db_path = database_module.DB_PATH
            database_module.DB_PATH = temp_db
            try:
                import config

                config.DATABASE = temp_db
                schema.create_database()

                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO career_sources (id, company, careers_url) VALUES (?, ?, ?)",
                        (1, "Acme", "https://example.com/careers"),
                    )
                    conn.execute(
                        "INSERT INTO career_sources (id, company, careers_url) VALUES (?, ?, ?)",
                        (2, "Globex", "https://example.org/careers"),
                    )
                    conn.execute(
                        "INSERT INTO career_jobs (id, career_source_id, title, company, url) VALUES (?, ?, ?, ?, ?)",
                        (1, 1, "QA Engineer", "Acme", "https://example.com/jobs/qa-engineer"),
                    )
                    conn.execute(
                        "INSERT INTO career_jobs (id, career_source_id, title, company, url) VALUES (?, ?, ?, ?, ?)",
                        (2, 2, "QA Engineer", "Globex", "https://example.com/jobs/qa-engineer/?ref=from-index"),
                    )
                    conn.commit()

                first = {
                    "page_not_found": False,
                    "title": "QA Engineer",
                    "company": "Acme",
                    "location": "Remote",
                    "remote": True,
                    "level": "Mid",
                    "contract": "CLT",
                    "job_source": "career",
                    "application_url": "https://example.com/apply/1",
                    "application_source": "career",
                    "description": "Build quality systems",
                    "technologies": ["Python", "Playwright"],
                    "requirements": ["Testing"],
                    "differentials": ["CI/CD"],
                    "benefits": ["Health plan"],
                }
                second = {**first, "title": "QA Engineer Updated", "company": "Globex"}

                insert_career_job_details(1, "https://example.com/jobs/qa-engineer", first)
                insert_career_job_details(2, "https://example.com/jobs/qa-engineer/?ref=from-index", second)

                with get_connection() as conn:
                    rows = conn.execute(
                        "SELECT career_job_id, source_url, title, company FROM career_job_details"
                    ).fetchall()

                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["career_job_id"], 2)
                self.assertEqual(rows[0]["title"], "QA Engineer Updated")
                self.assertEqual(rows[0]["company"], "Globex")
            finally:
                database_module.DB_PATH = original_db_path

    def test_technology_agent_counts_technology_frequency_from_database(self):
        import database.database as database_module
        from database.database import get_connection
        from database import schema
        from agents.technology_agent import TechnologyAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test.db"
            original_db_path = database_module.DB_PATH
            database_module.DB_PATH = temp_db
            try:
                import config

                config.DATABASE = temp_db
                schema.create_database()

                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO jobs (id, telegram_hash, link, title, company, category) VALUES (?, ?, ?, ?, ?, ?)",
                        (1, "hash-a", "https://example.com/a", "QA Engineer", "Acme", "QA"),
                    )
                    conn.execute(
                        "INSERT INTO jobs (id, telegram_hash, link, title, company, category) VALUES (?, ?, ?, ?, ?, ?)",
                        (2, "hash-b", "https://example.com/b", "QA Analyst", "Acme", "QA"),
                    )
                    conn.execute(
                        "INSERT INTO job_details (job_id, page_not_found, title, company, location, remote, level, contract, job_source, application_url, application_source, description, technologies, requirements, differentials, benefits, job_status, ai_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            1,
                            0,
                            "QA Engineer",
                            "Acme",
                            "Remote",
                            1,
                            "Junior",
                            "CLT",
                            "meupadrinho",
                            "https://example.com/apply/1",
                            "meupadrinho",
                            "Build software",
                            '["Playwright", "Python", "Playwright"]',
                            '[]',
                            '[]',
                            '[]',
                            'NEW',
                            'PENDING',
                        ),
                    )
                    conn.execute(
                        "INSERT INTO job_details (job_id, page_not_found, title, company, location, remote, level, contract, job_source, application_url, application_source, description, technologies, requirements, differentials, benefits, job_status, ai_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            2,
                            0,
                            "QA Analyst",
                            "Acme",
                            "Remote",
                            1,
                            "Pleno",
                            "CLT",
                            "meupadrinho",
                            "https://example.com/apply/2",
                            "meupadrinho",
                            "Test software",
                            '["Python", "Java"]',
                            '[]',
                            '[]',
                            '[]',
                            'NEW',
                            'PENDING',
                        ),
                    )
                    conn.commit()

                result = TechnologyAgent().analyze()
                self.assertEqual(result["jobs_with_technologies"], 2)
                self.assertEqual(result["technologies"]["PLAYWRIGHT"], 2)
                self.assertEqual(result["technologies"]["PYTHON"], 2)
            finally:
                database_module.DB_PATH = original_db_path


if __name__ == "__main__":
    unittest.main()
