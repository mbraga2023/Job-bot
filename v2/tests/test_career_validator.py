"""Unit tests for deterministic career title validation."""

from __future__ import annotations

import asyncio
import unittest

from v2.flows.careers.validator import (
    classify_title_with_ollama,
    extract_labeled_job_title,
)


class TestCareerValidatorTitleChecks(unittest.TestCase):
    def test_extracts_and_normalizes_labeled_title(self) -> None:
        title = extract_labeled_job_title(
            "Company: Example\nJob Title:\n  QA Engineer - Pleno  \nLocation: Remote"
        )
        self.assertEqual(title, "QA Engineer - Pleno")

    def test_rejects_unrelated_titles_without_calling_ollama(self) -> None:
        for title in (
            "Molder - Weekend Night Shift",
            "Turn your gaming skills into a career at Volvo Group",
        ):
            decision = asyncio.run(classify_title_with_ollama(title))
            self.assertFalse(decision["is_qa_mid_level"])
            self.assertEqual(decision["reason"], "TITLE_NOT_QA_ROLE")


if __name__ == "__main__":
    unittest.main()
