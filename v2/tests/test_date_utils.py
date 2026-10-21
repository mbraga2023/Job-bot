"""Unit Tests for Date Normalization and Staleness."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from v2.core.date_utils import (
    is_older_than_days,
    normalize_published_date,
    parse_relative_date,
)


class TestDateUtils(unittest.TestCase):
    def test_normalize_iso_date(self):
        self.assertEqual(normalize_published_date("2026-10-18T12:00:00Z"), "2026-10-18")
        self.assertEqual(normalize_published_date("2026-10-18"), "2026-10-18")

    def test_normalize_portuguese_date(self):
        self.assertEqual(normalize_published_date("18 de outubro de 2026"), "2026-10-18")
        self.assertEqual(normalize_published_date("5 de maio de 2026"), "2026-05-05")

    def test_relative_date(self):
        fixed_now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(normalize_published_date("hoje", now=fixed_now), "2026-10-20")
        self.assertEqual(normalize_published_date("ontem", now=fixed_now), "2026-10-19")
        self.assertEqual(normalize_published_date("há 2 dias", now=fixed_now), "2026-10-18")
        self.assertEqual(normalize_published_date("3 days ago", now=fixed_now), "2026-10-17")

    def test_staleness(self):
        fixed_now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        # 10 days old -> not stale
        self.assertFalse(is_older_than_days("2026-10-10", days=30, now=fixed_now))
        # 35 days old -> stale
        self.assertTrue(is_older_than_days("2026-09-10", days=30, now=fixed_now))


if __name__ == "__main__":
    unittest.main()
