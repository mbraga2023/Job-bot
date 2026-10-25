import unittest

from agents.analyzers.career import CareerAnalyzer
from core.keywords import QA_SEARCH_TERMS


class CareerKeywordTests(unittest.TestCase):
    def test_configured_terms_are_used_to_match_job_titles(self):
        for term in QA_SEARCH_TERMS:
            with self.subTest(term=term):
                self.assertIsNotNone(CareerAnalyzer.QA_PATTERN.search(term))

    def test_matching_is_case_insensitive_and_accepts_common_separators(self):
        self.assertIsNotNone(
            CareerAnalyzer.QA_PATTERN.search("Senior QUALITY-ENGINEER")
        )
        self.assertIsNotNone(
            CareerAnalyzer.QA_PATTERN.search("Analista_de_Testes")
        )

    def test_keyword_matches_require_word_boundaries(self):
        self.assertIsNone(CareerAnalyzer.QA_PATTERN.search("SDETester"))
        self.assertIsNone(CareerAnalyzer.QA_PATTERN.search("qualityish"))


if __name__ == "__main__":
    unittest.main()
