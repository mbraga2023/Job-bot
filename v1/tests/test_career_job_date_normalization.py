import unittest

from services.published_date import normalize_published_date


class PublishedDateNormalizationTests(unittest.TestCase):
    def test_iso_datetime_is_normalized_to_iso_date(self):
        self.assertEqual(
            normalize_published_date("2026-04-09T15:30:00Z"),
            "2026-04-09",
        )

    def test_brazilian_date_is_normalized_to_iso_date(self):
        self.assertEqual(
            normalize_published_date("22 de julho de 2026"),
            "2026-07-22",
        )

    def test_us_numeric_date_is_normalized_to_iso_date(self):
        self.assertEqual(
            normalize_published_date("9/23/26"),
            "2026-09-23",
        )

    def test_updated_suffix_is_removed(self):
        self.assertEqual(
            normalize_published_date(
                "August 16, 2026 (Updated about 9 hours ago)"
            ),
            "2026-08-16",
        )

    def test_weekday_prefix_is_supported(self):
        self.assertEqual(
            normalize_published_date("Tuesday, December 23, 2025"),
            "2025-12-23",
        )

    def test_non_date_text_is_missing(self):
        self.assertIsNone(normalize_published_date("Imediata"))

    def test_ambiguous_numeric_date_uses_month_first_order(self):
        self.assertEqual(
            normalize_published_date("6/12/26"),
            "2026-06-12",
        )

    def test_missing_date_is_none(self):
        self.assertIsNone(normalize_published_date(None))
