"""Unit Tests for Keywords and Technology Extraction."""

from __future__ import annotations

import unittest
from v2.core.keywords import (
    extract_technologies,
    is_qa_job_title,
    is_qa_related,
    is_non_qa_job_title,
    normalize_job_title,
)


class TestKeywords(unittest.TestCase):
    def test_qa_matching(self):
        self.assertTrue(is_qa_related("Senior QA Engineer"))
        self.assertTrue(is_qa_related("Analista de Testes"))
        self.assertTrue(is_qa_related("Software Quality Assurance Analyst"))
        self.assertTrue(is_qa_related("SDET - Automation"))
        self.assertTrue(is_qa_related("Engenheiro de Qualidade de Software"))

        self.assertFalse(is_qa_related("Frontend React Developer"))
        self.assertFalse(is_qa_related("Backend Java Engineer"))
        self.assertFalse(is_qa_related("Product Manager"))

    def test_extract_technologies(self):
        sample_text = """
        Requirements:
        Experience with Cypress and Playwright for UI automation.
        API testing using Postman and RestAssured.
        Knowledge of Python or TypeScript, SQL databases, and CI/CD with Docker.
        """
        techs = extract_technologies(sample_text)
        self.assertIn("Cypress", techs)
        self.assertIn("Playwright", techs)
        self.assertIn("Postman", techs)
        self.assertIn("RestAssured", techs)
        self.assertIn("Python", techs)
        self.assertIn("JavaScript / TypeScript", techs)
        self.assertIn("SQL", techs)
        self.assertIn("CI/CD", techs)
        self.assertIn("Docker", techs)

    def test_qa_title_filter_rejects_non_qa_and_promotional_titles(self):
        self.assertTrue(is_qa_job_title("QA Engineer - Pleno"))
        self.assertTrue(is_qa_job_title("Analista de Testes"))
        self.assertFalse(is_qa_job_title("Molder - Weekend Night Shift"))
        self.assertFalse(
            is_qa_job_title("Turn your gaming skills into a career at Volvo Group")
        )

    def test_explicit_non_qa_title_list_is_excluded(self):
        titles = (
            "Monitor de Qualidade",
            "Gerente Executivo de Qualidade",
            "Consultor de Validação",
            "Especialista em Desenvolvimento do Produto",
            "Pesquisador",
            "Inspetor de qualidade",
            "Analista de sistemas de gestão",
            "Analista de Controle de Qualidade Pleno",
            "Analista de negócios",
            "Analista de Monitoramento",
            "Gestão de qualidade",
            "Assistente de qualidade",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(is_non_qa_job_title(title))
                self.assertFalse(is_qa_job_title(title))
                self.assertFalse(is_qa_related(title))

        self.assertTrue(is_non_qa_job_title("ANALISTA DE NEGÓCIOS - Pleno"))

    def test_job_title_normalization_collapses_whitespace_and_entities(self):
        self.assertEqual(
            normalize_job_title("  QA Engineer\n (Pleno) &amp; Remote  "),
            "QA Engineer (Pleno) & Remote",
        )


if __name__ == "__main__":
    unittest.main()
