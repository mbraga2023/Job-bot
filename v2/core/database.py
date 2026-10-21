"""Centralized SQLite Database Manager & Repository for v2."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Sequence

from v2.config import config


def get_db_path() -> Path:
    """Return database path ensuring parent directory exists."""
    path = config.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Yield an open SQLite connection with foreign keys and dict row factory."""
    target_path = db_path or get_db_path()
    conn = sqlite3.connect(target_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """Create centralized tables and indexes if they do not exist."""
    with get_connection(db_path) as conn:
        # Table 1: Career Sources
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

        # Table 2: Centralized Jobs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Pipeline & Provenance
                pipeline TEXT NOT NULL,
                career_source_id INTEGER,
                external_id TEXT,
                telegram_hash TEXT,
                source_url TEXT NOT NULL UNIQUE,

                -- Discovered Attributes
                title TEXT,
                company TEXT,
                location TEXT,
                remote INTEGER DEFAULT 0,
                level TEXT,
                contract TEXT,
                category TEXT DEFAULT 'QA',

                -- Detailed Extraction Attributes
                application_url TEXT,
                application_source TEXT,
                description TEXT,
                technologies TEXT,
                requirements TEXT,
                differentials TEXT,
                benefits TEXT,
                published_date TEXT,
                raw_data TEXT,

                -- State Progression:
                -- DISCOVERED -> VALIDATED -> OPEN -> MANUAL (or DISCARDED / CLOSED / EXTRACTION_FAILED)
                status TEXT NOT NULL DEFAULT 'DISCOVERED',
                discard_reason TEXT,

                -- AI Title / Content Classification
                ai_status TEXT NOT NULL DEFAULT 'PENDING',
                ai_reason TEXT,

                -- Timestamps
                first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                validated_at DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(career_source_id) REFERENCES career_sources(id) ON DELETE SET NULL
            )
        """)

        # Indexes for fast querying
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_pipeline ON jobs(pipeline)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source_url ON jobs(source_url)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_validated_at ON jobs(validated_at)")
        conn.commit()


def migrate_career_sources_from_v1(v1_db_path: Path | None = None) -> int:
    """Migrate career_sources records from v1 database into v2 jobs_v2.db.

    Returns the number of migrated/imported sources.
    """
    v1_path = v1_db_path or config.v1_db_path
    if not v1_path.exists():
        raise FileNotFoundError(f"Source v1 database not found at {v1_path}")

    init_db()

    v1_conn = sqlite3.connect(v1_path)
    v1_conn.row_factory = sqlite3.Row
    try:
        rows = v1_conn.execute("""
            SELECT
                company,
                careers_url,
                search_url,
                source_type,
                api_url,
                api_method,
                api_config,
                active,
                last_checked_at,
                last_success_at,
                last_error,
                discovered_jobs,
                created_at,
                updated_at
            FROM career_sources
        """).fetchall()
    finally:
        v1_conn.close()

    if not rows:
        return 0

    with get_connection() as v2_conn:
        v2_conn.executemany("""
            INSERT INTO career_sources (
                company,
                careers_url,
                search_url,
                source_type,
                api_url,
                api_method,
                api_config,
                active,
                last_checked_at,
                last_success_at,
                last_error,
                discovered_jobs,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(careers_url) DO UPDATE SET
                company = excluded.company,
                search_url = COALESCE(excluded.search_url, career_sources.search_url),
                source_type = COALESCE(excluded.source_type, career_sources.source_type),
                api_url = COALESCE(excluded.api_url, career_sources.api_url),
                api_method = COALESCE(excluded.api_method, career_sources.api_method),
                api_config = COALESCE(excluded.api_config, career_sources.api_config),
                active = excluded.active,
                updated_at = CURRENT_TIMESTAMP
        """, [tuple(r) for r in rows])
        v2_conn.commit()

    return len(rows)


# =====================================================================
# Career Sources Repository
# =====================================================================

def get_active_career_sources() -> list[dict[str, Any]]:
    """Retrieve all active career sources ordered by company."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM career_sources
            WHERE active = 1
            ORDER BY company COLLATE NOCASE ASC
        """)
        return [dict(r) for r in cursor.fetchall()]


def insert_career_source(
    company: str,
    careers_url: str,
    search_url: str | None = None,
    source_type: str = "CAREER_PAGE",
) -> int:
    """Insert or ignore a career source."""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO career_sources (company, careers_url, search_url, source_type)
            VALUES (?, ?, ?, ?)
        """, (company.strip(), careers_url.strip(), search_url.strip() if search_url else None, source_type))
        conn.commit()
        return cursor.lastrowid or 0


def update_source_api_info(
    source_id: int,
    api_url: str,
    api_method: str = "GET",
    api_config: dict | None = None,
) -> None:
    """Update API details for a career source."""
    config_json = json.dumps(api_config) if api_config else None
    with get_connection() as conn:
        conn.execute("""
            UPDATE career_sources
            SET api_url = ?, api_method = ?, api_config = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (api_url, api_method, config_json, source_id))
        conn.commit()


def mark_source_checked(
    source_id: int,
    discovered_jobs: int = 0,
    error: str | None = None,
) -> None:
    """Record the timestamp and results of a career source scan."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        if error:
            conn.execute("""
                UPDATE career_sources
                SET last_checked_at = ?, last_error = ?, updated_at = ?
                WHERE id = ?
            """, (now, error, now, source_id))
        else:
            conn.execute("""
                UPDATE career_sources
                SET last_checked_at = ?, last_success_at = ?, last_error = NULL,
                    discovered_jobs = ?, updated_at = ?
                WHERE id = ?
            """, (now, now, discovered_jobs, now, source_id))
        conn.commit()


# =====================================================================
# Centralized Jobs Repository
# =====================================================================

def insert_discovered_job(
    pipeline: str,
    source_url: str,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    remote: int = 0,
    level: str | None = None,
    contract: str | None = None,
    category: str = "QA",
    career_source_id: int | None = None,
    external_id: str | None = None,
    telegram_hash: str | None = None,
    published_date: str | None = None,
    raw_data: dict | None = None,
) -> int | None:
    """Insert a new job in DISCOVERED status, or update last_seen_at if already present.

    Returns job id if inserted, None if duplicate.
    """
    raw_json = json.dumps(raw_data, ensure_ascii=False) if raw_data else None

    with get_connection() as conn:
        # Check existing
        existing = conn.execute(
            "SELECT id FROM jobs WHERE source_url = ?",
            (source_url,),
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE jobs
                SET last_seen_at = CURRENT_TIMESTAMP,
                    title = COALESCE(?, title),
                    company = COALESCE(?, company),
                    location = COALESCE(?, location)
                WHERE id = ?
            """, (title, company, location, existing["id"]))
            conn.commit()
            return None

        cursor = conn.execute("""
            INSERT INTO jobs (
                pipeline, career_source_id, external_id, telegram_hash,
                source_url, title, company, location, remote, level,
                contract, category, published_date, raw_data, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED')
        """, (
            pipeline, career_source_id, external_id, telegram_hash,
            source_url, title, company, location, remote, level,
            contract, category, published_date, raw_json,
        ))
        conn.commit()
        return cursor.lastrowid


def get_job_by_id(job_id: int) -> dict[str, Any] | None:
    """Fetch single job by its ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_job_by_source_url(source_url: str) -> dict[str, Any] | None:
    """Fetch single job by source URL."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE source_url = ?", (source_url,)).fetchone()
        return dict(row) if row else None


def update_job_validation(
    job_id: int,
    status: str,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    remote: int | None = None,
    level: str | None = None,
    contract: str | None = None,
    application_url: str | None = None,
    application_source: str | None = None,
    description: str | None = None,
    technologies: list[str] | str | None = None,
    requirements: str | None = None,
    differentials: str | None = None,
    benefits: str | None = None,
    published_date: str | None = None,
    discard_reason: str | None = None,
    ai_status: str | None = None,
    ai_reason: str | None = None,
) -> None:
    """Update job after stage 2 extraction/validation."""
    tech_str = json.dumps(technologies) if isinstance(technologies, list) else technologies
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute("""
            UPDATE jobs
            SET
                status = ?,
                title = COALESCE(?, title),
                company = COALESCE(?, company),
                location = COALESCE(?, location),
                remote = COALESCE(?, remote),
                level = COALESCE(?, level),
                contract = COALESCE(?, contract),
                application_url = COALESCE(?, application_url),
                application_source = COALESCE(?, application_source),
                description = COALESCE(?, description),
                technologies = COALESCE(?, technologies),
                requirements = COALESCE(?, requirements),
                differentials = COALESCE(?, differentials),
                benefits = COALESCE(?, benefits),
                published_date = COALESCE(?, published_date),
                discard_reason = ?,
                ai_status = COALESCE(?, ai_status),
                ai_reason = COALESCE(?, ai_reason),
                validated_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            status, title, company, location, remote, level, contract,
            application_url, application_source, description, tech_str,
            requirements, differentials, benefits, published_date,
            discard_reason, ai_status, ai_reason, now, now, job_id,
        ))
        conn.commit()


def update_job_status(job_id: int, status: str, discard_reason: str | None = None) -> None:
    """Update lifecycle status of a job."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            UPDATE jobs
            SET status = ?, discard_reason = COALESCE(?, discard_reason), updated_at = ?
            WHERE id = ?
        """, (status, discard_reason, now, job_id))
        conn.commit()


def get_jobs_for_validation(pipeline: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Get pending DISCOVERED jobs for validation."""
    query = "SELECT * FROM jobs WHERE pipeline = ? AND status = 'DISCOVERED' ORDER BY id ASC"
    params: list[Any] = [pipeline]
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_jobs_for_review(
    pipeline: str | None = None,
    statuses: Sequence[str] = ("VALIDATED", "OPEN"),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve eligible jobs to open in Chrome for review and manual application."""
    placeholders = ", ".join("?" for _ in statuses)
    conditions = [f"status IN ({placeholders})"]
    params: list[Any] = list(statuses)

    if pipeline:
        conditions.append("pipeline = ?")
        params.append(pipeline)

    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM jobs WHERE {where_clause} ORDER BY id DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_database_stats() -> dict[str, Any]:
    """Retrieve summary counts from centralized database for dashboard reporting."""
    init_db()
    with get_connection() as conn:
        # Total sources
        sources_count = conn.execute("SELECT count(*) FROM career_sources").fetchone()[0]
        sources_active = conn.execute("SELECT count(*) FROM career_sources WHERE active = 1").fetchone()[0]

        # Overall job counts
        total_jobs = conn.execute("SELECT count(*) FROM jobs").fetchone()[0]

        # Jobs by pipeline
        by_pipeline = {}
        for row in conn.execute("SELECT pipeline, count(*) as cnt FROM jobs GROUP BY pipeline"):
            by_pipeline[row["pipeline"]] = row["cnt"]

        # Jobs by status
        by_status = {}
        for row in conn.execute("SELECT status, count(*) as cnt FROM jobs GROUP BY status"):
            by_status[row["status"]] = row["cnt"]

        # Discard reasons
        by_discard = {}
        for row in conn.execute("SELECT discard_reason, count(*) as cnt FROM jobs WHERE status = 'DISCARDED' AND discard_reason IS NOT NULL GROUP BY discard_reason"):
            by_discard[row["discard_reason"]] = row["cnt"]

        return {
            "career_sources_total": sources_count,
            "career_sources_active": sources_active,
            "jobs_total": total_jobs,
            "jobs_by_pipeline": by_pipeline,
            "jobs_by_status": by_status,
            "jobs_by_discard_reason": by_discard,
        }
