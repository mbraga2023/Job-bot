#/database/career_sources.py
import json

from database.database import get_connection


def create_career_sources_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS career_sources (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            company TEXT NOT NULL,

            careers_url TEXT NOT NULL UNIQUE,

            search_url TEXT,

            source_type TEXT DEFAULT 'CAREER_PAGE',

            api_url TEXT,

            api_method TEXT,

            api_config TEXT,

            active INTEGER DEFAULT 1,

            last_checked_at DATETIME,

            last_success_at DATETIME,

            last_error TEXT,

            discovered_jobs INTEGER DEFAULT 0,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP

        )
        """)

        conn.commit()


def get_all_career_sources():

    with get_connection() as conn:

        cursor = conn.execute("""
            SELECT
                id,
                company,
                careers_url,
                search_url,
                source_type,
                active
            FROM career_sources
            WHERE active = 1
            ORDER BY company
        """)

        return cursor.fetchall()


def get_career_source_by_url(url):

    with get_connection() as conn:

        cursor = conn.execute("""
            SELECT *
            FROM career_sources
            WHERE careers_url = ?
        """, (url,))

        return cursor.fetchone()


def insert_career_source(
    company: str,
    careers_url: str,
    search_url: str | None = None,
    source_type: str = "CAREER_PAGE",
):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO career_sources (

                company,
                careers_url,
                search_url,
                source_type

            )

            VALUES (?, ?, ?, ?)
            """,
            (
                company,
                careers_url,
                search_url,
                source_type,
            ),
        )

        conn.commit()

        return cursor.lastrowid if cursor.rowcount == 1 else None


def insert_career_sources(sources: list[dict]) -> tuple[int, int]:
    inserted = 0

    with get_connection() as conn:
        for source in sources:
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
                    source["company"],
                    source["careers_url"],
                    source["search_url"],
                    "CAREER_PAGE",
                    1,
                ),
            )
            inserted += cursor.rowcount

        conn.commit()

    return inserted, len(sources) - inserted


def get_career_sources(active_only: bool = True):

    with get_connection() as conn:

        if active_only:

            cursor = conn.execute(
                """
                SELECT *

                FROM career_sources

                WHERE active = 1

                ORDER BY company
                """
            )

        else:

            cursor = conn.execute(
                """
                SELECT *

                FROM career_sources

                ORDER BY company
                """
            )

        return cursor.fetchall()


def get_career_source(source_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM career_sources

            WHERE id = ?
            """,
            (source_id,),
        )

        return cursor.fetchone()


def update_career_source_status(
    source_id: int,
    source_type: str | None = None,
    api_url: str | None = None,
    api_method: str | None = None,
    api_config: dict | None = None,
    last_error: str | None = None,
    discovered_jobs: int | None = None,
):

    fields = []
    values = []

    if source_type is not None:

        fields.append("source_type = ?")
        values.append(source_type)

    if api_url is not None:

        fields.append("api_url = ?")
        values.append(api_url)

    if api_method is not None:

        fields.append("api_method = ?")
        values.append(api_method)

    if api_config is not None:

        fields.append("api_config = ?")

        values.append(
            json.dumps(
                api_config,
                ensure_ascii=False,
            )
        )

    if last_error is not None:

        fields.append("last_error = ?")
        values.append(last_error)

    if discovered_jobs is not None:

        fields.append("discovered_jobs = ?")
        values.append(discovered_jobs)

    if not fields:
        return

    values.append(source_id)

    with get_connection() as conn:

        conn.execute(
            f"""
            UPDATE career_sources

            SET
                {", ".join(fields)}

            WHERE id = ?
            """,
            values,
        )

        conn.commit()


def mark_source_checked(
    source_id: int,
    success: bool,
    error: str | None = None,
):

    with get_connection() as conn:

        if success:

            conn.execute(
                """
                UPDATE career_sources

                SET
                    last_checked_at = CURRENT_TIMESTAMP,
                    last_success_at = CURRENT_TIMESTAMP,
                    last_error = NULL

                WHERE id = ?
                """,
                (source_id,),
            )

        else:

            conn.execute(
                """
                UPDATE career_sources

                SET
                    last_checked_at = CURRENT_TIMESTAMP,
                    last_error = ?

                WHERE id = ?
                """,
                (
                    error,
                    source_id,
                ),
            )

        conn.commit()