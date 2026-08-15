#/database/career_jobs.py
import json

from database.database import get_connection

def create_career_jobs_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS career_jobs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            career_source_id INTEGER NOT NULL,

            external_id TEXT,

            title TEXT,

            company TEXT,

            location TEXT,

            url TEXT NOT NULL,

            published_date TEXT,

            raw_data TEXT,

            first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            active INTEGER DEFAULT 1,

            UNIQUE(career_source_id, url),

            FOREIGN KEY(career_source_id)
                REFERENCES career_sources(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()

def insert_career_job(
    career_source_id: int,
    title: str | None,
    company: str | None,
    location: str | None,
    url: str,
    external_id: str | None = None,
    published_date: str | None = None,
    raw_data: dict | None = None,
):

    raw_json = None

    if raw_data is not None:

        raw_json = json.dumps(
            raw_data,
            ensure_ascii=False,
        )

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO career_jobs (

                career_source_id,
                external_id,
                title,
                company,
                location,
                url,
                published_date,
                raw_data

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(career_source_id, url)

            DO UPDATE SET

                external_id = excluded.external_id,
                title = excluded.title,
                company = excluded.company,
                location = excluded.location,
                published_date = excluded.published_date,
                raw_data = excluded.raw_data,
                last_seen_at = CURRENT_TIMESTAMP,
                active = 1
            """,
            (
                career_source_id,
                external_id,
                title,
                company,
                location,
                url,
                published_date,
                raw_json,
            ),
        )

        conn.commit()

        return cursor.lastrowid


def get_career_jobs(
    career_source_id: int | None = None,
    active_only: bool = True,
):

    with get_connection() as conn:

        conditions = []
        params = []

        if career_source_id is not None:

            conditions.append(
                "career_source_id = ?"
            )

            params.append(
                career_source_id
            )

        if active_only:

            conditions.append(
                "active = 1"
            )

        where_clause = ""

        if conditions:

            where_clause = (
                "WHERE "
                + " AND ".join(conditions)
            )

        cursor = conn.execute(
            f"""
            SELECT *

            FROM career_jobs

            {where_clause}

            ORDER BY last_seen_at DESC
            """,
            params,
        )

        return cursor.fetchall()


def deactivate_missing_jobs(
    career_source_id: int,
    active_urls: list[str],
):

    with get_connection() as conn:

        if not active_urls:

            conn.execute(
                """
                UPDATE career_jobs

                SET active = 0

                WHERE career_source_id = ?
                """,
                (career_source_id,),
            )

        else:

            placeholders = ",".join(
                "?" for _ in active_urls
            )

            conn.execute(
                f"""
                UPDATE career_jobs

                SET active = 0

                WHERE
                    career_source_id = ?
                    AND url NOT IN ({placeholders})
                """,
                [
                    career_source_id,
                    *active_urls,
                ],
            )

        conn.commit()