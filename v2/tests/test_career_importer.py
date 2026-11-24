"""Tests for importing career sources."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from v2.flows.careers import importer


class TestCareerSourceImporter(unittest.TestCase):
    def test_import_json_trims_values_and_counts_inserted_skipped_and_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            json_path = Path(temporary_directory) / "sources.json"
            json_path.write_text(json.dumps([
                {
                    "company": " Acme ",
                    "careers_url": " https://acme.example/careers ",
                    "search_url": " ",
                    "source_type": " ATS ",
                },
                {
                    "company": "Duplicate",
                    "careers_url": "https://duplicate.example/careers",
                },
                {"company": "Missing URL"},
                {"careers_url": "https://missing.example/careers"},
            ]), encoding="utf-8")

            with (
                patch.object(importer, "insert_career_source", side_effect=[12, 0]) as insert_source,
                redirect_stdout(StringIO()),
            ):
                result = importer.import_sources_from_json(json_path)

        self.assertEqual(result, {"inserted": 1, "skipped": 3})
        self.assertEqual(insert_source.call_args_list[0].kwargs, {
            "company": "Acme",
            "careers_url": "https://acme.example/careers",
            "search_url": None,
            "source_type": "ATS",
        })
        self.assertEqual(insert_source.call_args_list[1].kwargs["source_type"], "CAREER_PAGE")

    def test_import_json_raises_for_missing_file_and_non_array_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                importer.import_sources_from_json(missing_path)

            json_path = Path(temporary_directory) / "not-an-array.json"
            json_path.write_text(json.dumps({"company": "Acme"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must contain an array"):
                importer.import_sources_from_json(json_path)

    def test_import_payload_counts_valid_and_incomplete_sources(self) -> None:
        with patch.object(importer, "insert_career_source", side_effect=[7, 0]) as insert_source:
            result = importer.import_sources_from_payload([
                {
                    "company": "Acme",
                    "careers_url": "https://acme.example/careers",
                    "source_type": "GUPY",
                },
                {"company": "Missing URL"},
                {
                    "company": "Duplicate",
                    "careers_url": "https://duplicate.example/careers",
                },
            ])

        self.assertEqual(result, {"inserted": 1, "skipped": 2})
        self.assertEqual(insert_source.call_args_list[0].kwargs["source_type"], "GUPY")


if __name__ == "__main__":
    unittest.main()
