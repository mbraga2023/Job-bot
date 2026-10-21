"""Unit Tests for Data Migration from v1 to v2."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v2.config import config
from v2.core.database import (
    get_active_career_sources,
    init_db,
    migrate_career_sources_from_v1,
)


class TestMigration(unittest.TestCase):
    def test_migration_from_v1_database(self):
        v1_path = config.root_dir / "database" / "jobs.db"
        if not v1_path.exists():
            self.skipTest("v1 jobs.db not found on disk")

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "jobs_v2_test.db"
            orig_db = config.db_path
            try:
                config.db_path = temp_db
                init_db(temp_db)

                count = migrate_career_sources_from_v1(v1_path)
                self.assertGreater(count, 0)

                active = get_active_career_sources()
                self.assertEqual(len(active), count)

                # Verify first few have valid URLs
                for src in active[:5]:
                    self.assertTrue(src["company"])
                    self.assertTrue(src["careers_url"].startswith("http"))
            finally:
                config.db_path = orig_db


if __name__ == "__main__":
    unittest.main()
