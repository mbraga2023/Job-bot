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

    def test_linkedin_application_url_extraction(self):
        import asyncio

        from agents.analyzers.linkedin import LinkedInAnalyzer

        class LinkLocator:
            first = None

            def __init__(self, href):
                self.href = href
                self.first = self

            async def count(self):
                return 1

            async def get_attribute(self, name):
                return self.href

        class FakePage:
            url = "https://www.linkedin.com/jobs/view/123/"

            def get_by_role(self, role, name):
                return LinkLocator("/jobs/view/456/")

        application_url = asyncio.run(
            LinkedInAnalyzer().get_application_url(FakePage())
        )
        self.assertEqual(
            application_url,
            "https://www.linkedin.com/jobs/view/456/",
        )

    def test_linkedin_queue_includes_meupadrinho_urls_and_updates_application_url(self):
        import sqlite3
        from unittest.mock import patch

        from database.job_details import (
            get_linkedin_jobs,
            update_application_url,
        )

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """
                CREATE TABLE job_details (
                    job_id INTEGER PRIMARY KEY,
                    application_url TEXT,
                    job_status TEXT,
                    job_source TEXT,
                    title TEXT,
                    company TEXT,
                    validated_at TEXT
                )
                """
            )
            conn.executemany(
                "INSERT INTO job_details VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (1, "https://meupadrinho.com.br/vaga/1", "NEW", "LinkedIn", "QA", "Acme", "2026-01-03"),
                    (2, "https://www.linkedin.com/jobs/view/2", "NEW", "linkedin", "SDET", "Beta", "2026-01-02"),
                    (3, "https://www.linkedin.com/jobs/view/3", "NEW", "Indeed", "QA", "Gamma", "2026-01-01"),
                ],
            )

            with patch(
                "database.job_details.get_connection",
                return_value=conn,
            ):
                jobs = get_linkedin_jobs()
                update_application_url(
                    1,
                    "https://www.linkedin.com/jobs/view/1",
                )

            self.assertEqual(
                {job["job_id"] for job in jobs},
                {1, 2},
            )
            self.assertEqual(
                conn.execute(
                    "SELECT application_url FROM job_details WHERE job_id = 1"
                ).fetchone()[0],
                "https://www.linkedin.com/jobs/view/1",
            )
        finally:
            conn.close()

    def test_indeed_agent_extracts_job_posting_from_json_ld(self):
        from agents.indeed_agent import (
            _contains_target_keyword,
            _find_job_posting,
            _is_verification_page,
            _parse_saved_html,
            _plain_text,
        )

        structured_data = {
            "@graph": [
                {
                    "@type": "Organization",
                    "name": "Indeed",
                },
                {
                    "@type": "JobPosting",
                    "title": "QA Engineer",
                    "description": "<p>Test <strong>web applications</strong>.</p>",
                    "hiringOrganization": {"name": "Acme"},
                },
            ]
        }

        posting = _find_job_posting(structured_data)
        self.assertEqual(posting["title"], "QA Engineer")
        self.assertEqual(posting["hiringOrganization"]["name"], "Acme")
        self.assertEqual(
            _plain_text(posting["description"]),
            "Test web applications.",
        )
        self.assertTrue(
            _is_verification_page(
                "Just a moment...",
                "Additional Verification Required",
                "https://br.indeed.com/viewjob",
            )
        )
        self.assertFalse(
            _is_verification_page(
                "QA Engineer",
                "Acme is hiring a QA Engineer",
                "https://br.indeed.com/viewjob",
            )
        )
        self.assertTrue(_contains_target_keyword("Analista de Qualidade Pleno"))
        self.assertTrue(_contains_target_keyword("[MP] ANALISTA DE QA PLENO"))
        self.assertTrue(_contains_target_keyword("Senior Quality Assurance"))
        self.assertFalse(_contains_target_keyword("Quality Technician"))

        snapshot = _parse_saved_html(
            """
            <!-- saved from url=(050)https://br.indeed.com/jobs?vjk=qa123 -->
            <div class="cardOutline">
                <a class="jcs-JobTitle" data-jk="qa123" href="/rc/clk?jk=qa123">
                    Analista de Qualidade Pleno
                </a>
                <div class="companyName">Acme</div>
                <div class="companyLocation">Campinas, SP</div>
                <div class="jobMetaDataGroup">Automação de testes</div>
            </div>
            <div data-testid="viewjob-main-content">
                <h5 data-testid="vj-job-title">Analista de Qualidade Pleno</h5>
                <a href="https://br.indeed.com/cmp/Acme">Acme</a>
                <div id="jobDetailsSection">Descrição completa da vaga.</div>
                <div data-testid="primary-apply-action">
                    <a data-testid="viewjob-indeed-apply" href="https://employer.example/apply">
                        Candidatar-se no site da Empresa
                    </a>
                </div>
            </div>
            """
        )
        self.assertEqual(len(snapshot["matching_jobs"]), 1)
        self.assertEqual(snapshot["matching_jobs"][0]["company"], "Acme")
        self.assertEqual(
            snapshot["selected_pane"]["application_actions"][0]["url"],
            "https://employer.example/apply",
        )

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
