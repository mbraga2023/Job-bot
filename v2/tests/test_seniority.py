"""Unit Tests for Canonical Seniority Evaluator."""

from __future__ import annotations

import unittest
from v2.core.seniority import evaluate_seniority


class TestSeniorityEvaluator(unittest.TestCase):
    def test_eligible_mid_level(self):
        cases = [
            ("QA Engineer Pleno", None),
            ("Analista de Testes", "Pleno"),
            ("Software Quality Engineer", "Mid-Level"),
            ("Test Automation Engineer", "Middle"),
            ("QA Analyst", None),  # unstated level is accepted
        ]
        for title, level in cases:
            with self.subTest(title=title, level=level):
                ok, reason = evaluate_seniority(title, level)
                self.assertTrue(ok, f"Expected {title} ({level}) to be eligible")
                self.assertIsNone(reason)

    def test_combined_mid_and_senior(self):
        # Explicit combination including Pleno must be accepted
        cases = [
            ("QA Testing Pleno/Senior", None),
            ("Analista de Qualidade", "Pleno/Senior"),
            ("QA Engineer", "Mid-Senior"),
            ("Engenheiro de Testes", "Pleno / Sênior"),
        ]
        for title, level in cases:
            with self.subTest(title=title, level=level):
                ok, reason = evaluate_seniority(title, level)
                self.assertTrue(ok, f"Expected combined level {title} ({level}) to be accepted")
                self.assertIsNone(reason)

    def test_discard_junior_and_intern(self):
        cases = [
            ("QA Engineer Junior", None),
            ("Analista de Testes Jr", None),
            ("Estágio em Qualidade de Software", None),
            ("QA Intern", None),
            ("Trainee em Testes", None),
            ("QA Analyst", "Júnior"),
            ("Tester", "Estagiário"),
        ]
        for title, level in cases:
            with self.subTest(title=title, level=level):
                ok, reason = evaluate_seniority(title, level)
                self.assertFalse(ok, f"Expected {title} ({level}) to be discarded")
                self.assertEqual(reason, "SENIORITY_JUNIOR")

    def test_discard_senior_and_lead(self):
        cases = [
            ("Senior QA Automation Engineer", None),
            ("Analista de Testes Sênior", None),
            ("QA Tech Lead", None),
            ("Principal QA Architect", None),
            ("QA Manager", None),
            ("Gerente de Qualidade", None),
            ("Especialista em Testes", None),
            ("QA Engineer", "Sr"),
            ("SDET", "Senior"),
        ]
        for title, level in cases:
            with self.subTest(title=title, level=level):
                ok, reason = evaluate_seniority(title, level)
                self.assertFalse(ok, f"Expected {title} ({level}) to be discarded")
                self.assertEqual(reason, "SENIORITY_SENIOR")


if __name__ == "__main__":
    unittest.main()
