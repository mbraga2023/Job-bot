import argparse
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.published_date import normalize_published_date


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize career_job_details.published_date to YYYY-MM-DD."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / "database" / "jobs.db",
        help="SQLite database path (defaults to database/jobs.db).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes after creating a timestamped database backup.",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.is_file():
        parser.error(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(career_job_details)"
            )
        }
        if not {"id", "published_date"}.issubset(columns):
            parser.error(
                "career_job_details is missing id or published_date."
            )

        records = connection.execute(
            "SELECT id, published_date FROM career_job_details"
        ).fetchall()

        changes = []
        change_summary = Counter()
        invalid_summary = Counter()

        for row_id, old_value in records:
            if not isinstance(old_value, str) or not old_value.strip():
                continue

            normalized = normalize_published_date(old_value)
            if normalized is None:
                invalid_summary[old_value] += 1

            if normalized != old_value:
                changes.append((normalized, row_id))
                change_summary[(old_value, normalized)] += 1

        mode = "APPLY" if args.apply else "DRY RUN"
        print(f"Mode: {mode}")
        print(f"Database: {database_path}")
        print(f"Rows scanned: {len(records)}")
        print(f"Rows to update: {len(changes)}")

        if change_summary:
            print("\nProposed changes:")
            for (old_value, normalized), count in sorted(change_summary.items()):
                target = normalized if normalized is not None else "NULL"
                print(f"{count:>4}  {old_value!r} -> {target}")

        if invalid_summary:
            print("\nUnrecognized values will be set to NULL:")
            for value, count in sorted(invalid_summary.items()):
                print(f"{count:>4}  {value!r}")

        if not args.apply or not changes:
            if args.apply and not changes:
                print("\nNo changes needed.")
            elif changes:
                print("\nNo data changed. Rerun with --apply to write these changes.")
            return 0

        backup_path = database_path.with_name(
            f"{database_path.stem}.backup-"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            f"{database_path.suffix}"
        )
        with sqlite3.connect(backup_path) as backup:
            connection.backup(backup)

        with connection:
            connection.executemany(
                "UPDATE career_job_details SET published_date = ? WHERE id = ?",
                changes,
            )

        print(f"\nUpdated {len(changes)} rows.")
        print(f"Backup: {backup_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())