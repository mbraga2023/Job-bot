import json
from pathlib import Path

from database.database import get_connection


def import_career_sources(json_path: str):

    path = Path(json_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Career sources JSON not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        sources = json.load(file)

    if not isinstance(sources, list):
        raise ValueError(
            "Career sources JSON must contain a list."
        )

    inserted = 0
    skipped = 0

    with get_connection() as conn:

        for source in sources:

            company = (
                source.get("company") or ""
            ).strip()

            careers_url = (
                source.get("careers_url") or ""
            ).strip()

            search_url = (
                source.get("search_url") or ""
            ).strip()

            if not search_url:
                search_url = None

            # -----------------------------------------------------
            # Validate required fields
            # -----------------------------------------------------

            if not company or not careers_url:

                print(
                    "⚠ Skipping invalid entry:"
                    f" {source}"
                )

                skipped += 1
                continue

            # -----------------------------------------------------
            # Insert career source
            # -----------------------------------------------------

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO career_sources (

                    company,
                    careers_url,
                    search_url,
                    source_type,
                    active

                )

                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    company,
                    careers_url,
                    search_url,
                    "CAREER_PAGE",
                    1,
                ),
            )

            # -----------------------------------------------------
            # Result
            # -----------------------------------------------------

            if cursor.rowcount == 1:

                inserted += 1

                print(
                    f"✓ Added: "
                    f"{company} -> {careers_url}"
                )

                if search_url:

                    print(
                        f"  Search URL: "
                        f"{search_url}"
                    )

            else:

                skipped += 1

                print(
                    f"→ Already exists: "
                    f"{company}"
                )

        conn.commit()

    print()
    print("=============================")
    print("Career source import finished")
    print("=============================")
    print(f"Inserted : {inserted}")
    print(f"Skipped  : {skipped}")
    print("=============================")