import sqlite3
from pathlib import Path

DB_FOLDER = Path("database")
DB_FOLDER.mkdir(exist_ok=True)

DB_PATH = DB_FOLDER / "jobs.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            telegram_hash TEXT UNIQUE,

            title TEXT,
            company TEXT,
            location TEXT,
            contract TEXT,
            level TEXT,
            link TEXT,

            category TEXT,
            remote INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,

            applied INTEGER DEFAULT 0,

            notes TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP

        )
        """)

        conn.commit()


def job_exists(hash_value):

    with get_connection() as conn:

        cursor = conn.execute(
            "SELECT 1 FROM jobs WHERE telegram_hash = ?",
            (hash_value,)
        )

        return cursor.fetchone() is not None


def insert_job(job):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO jobs (

                telegram_hash,

                title,
                company,
                location,
                contract,
                level,
                link,

                category,
                remote,
                score

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            job["telegram_hash"],

            job["title"],
            job["company"],
            job["location"],
            job["contract"],
            job["level"],
            job["link"],

            job["category"],
            int(job["remote"]),
            job["score"]

        ))

        conn.commit()


def get_all_jobs():

    with get_connection() as conn:

        cursor = conn.execute("""

            SELECT

                id,
                score,
                category,
                remote,
                title,
                company,
                location,
                contract,
                level,
                applied,
                link,
                created_at

            FROM jobs

            ORDER BY score DESC,
                     created_at DESC

        """)

        return cursor.fetchall()


def get_statistics():

    with get_connection() as conn:

        total = conn.execute(
            "SELECT COUNT(*) FROM jobs"
        ).fetchone()[0]

        qa = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE category='QA'"
        ).fetchone()[0]

        remote = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE remote=1"
        ).fetchone()[0]

        applied = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE applied=1"
        ).fetchone()[0]

    return {
        "total": total,
        "qa": qa,
        "remote": remote,
        "applied": applied
    }