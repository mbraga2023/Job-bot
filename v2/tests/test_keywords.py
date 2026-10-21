"""Unit Tests for Keywords and Technology Extraction."""

from __future__ import annotations

import unittest
from v2.core.keywords import extract_technologies, is_qa_related


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


if __name__ == "__main__":
    unittest.main()
