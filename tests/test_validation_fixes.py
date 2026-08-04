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


if __name__ == "__main__":
    unittest.main()
