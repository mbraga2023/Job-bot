import json
from urllib.parse import urlsplit, urlunsplit

from core.job_status import (
    DEFAULT_JOB_STATUS,
    JOB_STATUS,
)

from database.database import get_connection
from services.published_date import normalize_published_date


# =========================================================
# Create
# =========================================================

def create_career_job_details_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS career_job_details (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            career_job_id INTEGER NOT NULL UNIQUE,

            source_url TEXT NOT NULL UNIQUE,

            page_not_found INTEGER DEFAULT 0,

            published_date TEXT,

            title TEXT,
            company TEXT,
            location TEXT,

            remote INTEGER DEFAULT 0,

            level TEXT,
            contract TEXT,

            job_source TEXT,

            application_url TEXT,

            application_source TEXT,

            description TEXT,

            technologies TEXT,

            requirements TEXT,

            differentials TEXT,

            benefits TEXT,

            job_status TEXT NOT NULL DEFAULT 'NEW',

            ai_status TEXT NOT NULL DEFAULT 'PENDING',

            validated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(career_job_id)
                REFERENCES career_jobs(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()


# =========================================================
# URL
# =========================================================

def normalize_url(url: str) -> str:
    """
    Normalize a career job URL before comparing/storing it.

    Removes:
    - query string
    - fragment
    - trailing slash

    Keeps:
    - scheme
    - hostname
    - path
    """

    value = (url or "").strip()

    if not value:
        return ""

    parts = urlsplit(value)

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    path = parts.path.rstrip("/")

    if not path:
        path = "/"

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            "",
            "",
        )
    )


# =========================================================
# Validation Queue
# =========================================================

def get_generic_job_links(limit: int | None = 20):

    with get_connection() as conn:

        # -------------------------------------------------
        # Get active career jobs
        # -------------------------------------------------

        cursor = conn.execute(
            """
            SELECT *

            FROM career_jobs

            WHERE active = 1

            ORDER BY last_seen_at DESC
            """
        )

        career_jobs = cursor.fetchall()

        # -------------------------------------------------
        # Get URLs already represented in details
        # -------------------------------------------------

        cursor = conn.execute(
            """
            SELECT career_job_id, source_url

            FROM career_job_details
            """
        )

        existing_details = cursor.fetchall()
        existing_urls = {
            normalize_url(row["source_url"])
            for row in existing_details
        }
        existing_job_ids = {
            row["career_job_id"]
            for row in existing_details
        }

    # -----------------------------------------------------
    # Filter before Playwright validation
    # -----------------------------------------------------

    pending_jobs = []

    for job in career_jobs:

        normalized_url = normalize_url(
            job["url"]
        )

        if not normalized_url:
            continue

        if job["id"] in existing_job_ids or normalized_url in existing_urls:
            continue

        pending_jobs.append(job)

        if limit is not None and len(pending_jobs) >= limit:
            break

    return pending_jobs


# =========================================================
# Exists
# =========================================================

def career_job_details_exists(
    career_job_id: int,
) -> bool:

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT 1

            FROM career_job_details

            WHERE career_job_id = ?

            LIMIT 1
            """,
            (career_job_id,),
        )

        return cursor.fetchone() is not None


def career_job_url_exists(
    source_url: str,
) -> bool:

    normalized_url = normalize_url(
        source_url
    )

    if not normalized_url:
        return False

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT 1

            FROM career_job_details

            WHERE source_url = ?

            LIMIT 1
            """,
            (normalized_url,),
        )

        return cursor.fetchone() is not None


# =========================================================
# Create
# =========================================================

def insert_career_job_details(
    career_job_id: int,
    source_url: str,
    details: dict,
) -> int:
    """
    Saves validated career job details collected by Playwright.
    """

    normalized_url = normalize_url(
        source_url
    )

    if not normalized_url:
        raise ValueError(
            "source_url cannot be empty"
        )

    published_date = normalize_published_date(details.get("published_date"))

    with get_connection() as conn:

        existing = conn.execute(
            """
            SELECT id, career_job_id

            FROM career_job_details

            WHERE source_url = ?
            LIMIT 1
            """,
            (normalized_url,),
        ).fetchone()

        if existing is not None:
            row_id = existing["id"]

            if existing["career_job_id"] == career_job_id:
                conn.execute(
                    """
                    UPDATE career_job_details

                    SET
                        page_not_found = ?,
                        published_date = ?,
                        title = ?,
                        company = ?,
                        location = ?,
                        remote = ?,
                        level = ?,
                        contract = ?,
                        job_source = ?,
                        application_url = ?,
                        application_source = ?,
                        description = ?,
                        technologies = ?,
                        requirements = ?,
                        differentials = ?,
                        benefits = ?,
                        job_status = ?,
                        ai_status = ?,
                        validated_at = CURRENT_TIMESTAMP

                    WHERE id = ?
                    """,
                    (
                        int(details.get("page_not_found", False)),
                        published_date,
                        details.get("title"),
                        details.get("company"),
                        details.get("location"),
                        int(details.get("remote", False)),
                        details.get("level"),
                        details.get("contract"),
                        details.get("job_source"),
                        details.get("application_url"),
                        details.get("application_source"),
                        details.get("description"),
                        json.dumps(details.get("technologies", []), ensure_ascii=False),
                        json.dumps(details.get("requirements", []), ensure_ascii=False),
                        json.dumps(details.get("differentials", []), ensure_ascii=False),
                        json.dumps(details.get("benefits", []), ensure_ascii=False),
                        details.get("job_status", DEFAULT_JOB_STATUS),
                        details.get("ai_status", "PENDING"),
                        row_id,
                    ),
                )
                conn.commit()
                return row_id

            conn.execute(
                """
                UPDATE career_job_details

                SET
                    career_job_id = ?,
                    page_not_found = ?,
                    published_date = ?,
                    title = ?,
                    company = ?,
                    location = ?,
                    remote = ?,
                    level = ?,
                    contract = ?,
                    job_source = ?,
                    application_url = ?,
                    application_source = ?,
                    description = ?,
                    technologies = ?,
                    requirements = ?,
                    differentials = ?,
                    benefits = ?,
                    job_status = ?,
                    ai_status = ?,
                    validated_at = CURRENT_TIMESTAMP

                WHERE source_url = ?
                """,
                (
                    career_job_id,
                    int(details.get("page_not_found", False)),
                    published_date,
                    details.get("title"),
                    details.get("company"),
                    details.get("location"),
                    int(details.get("remote", False)),
                    details.get("level"),
                    details.get("contract"),
                    details.get("job_source"),
                    details.get("application_url"),
                    details.get("application_source"),
                    details.get("description"),
                    json.dumps(details.get("technologies", []), ensure_ascii=False),
                    json.dumps(details.get("requirements", []), ensure_ascii=False),
                    json.dumps(details.get("differentials", []), ensure_ascii=False),
                    json.dumps(details.get("benefits", []), ensure_ascii=False),
                    details.get("job_status", DEFAULT_JOB_STATUS),
                    details.get("ai_status", "PENDING"),
                    normalized_url,
                ),
            )
            conn.commit()
            return existing["id"]

        cursor = conn.execute(
            """
            INSERT INTO career_job_details (

                career_job_id,

                source_url,

                page_not_found,

                published_date,

                title,
                company,
                location,

                remote,

                level,
                contract,

                job_source,

                application_url,

                application_source,

                description,

                technologies,
                requirements,
                differentials,
                benefits,

                job_status,

                ai_status

            )

            VALUES (

                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?

            )
            """,
            (
                career_job_id,

                normalized_url,

                int(
                    details.get(
                        "page_not_found",
                        False,
                    )
                ),

                details.get(
                    "published_date"
                ),

                details.get("title"),
                details.get("company"),
                details.get("location"),

                int(
                    details.get(
                        "remote",
                        False,
                    )
                ),

                details.get("level"),
                details.get("contract"),

                details.get("job_source"),

                details.get("application_url"),

                details.get(
                    "application_source"
                ),

                details.get("description"),

                json.dumps(
                    details.get(
                        "technologies",
                        [],
                    ),
                    ensure_ascii=False,
                ),

                json.dumps(
                    details.get(
                        "requirements",
                        [],
                    ),
                    ensure_ascii=False,
                ),

                json.dumps(
                    details.get(
                        "differentials",
                        [],
                    ),
                    ensure_ascii=False,
                ),

                json.dumps(
                    details.get(
                        "benefits",
                        [],
                    ),
                    ensure_ascii=False,
                ),

                details.get(
                    "job_status",
                    DEFAULT_JOB_STATUS,
                ),

                details.get("ai_status", "PENDING"),
            ),
        )

        conn.commit()

        return cursor.lastrowid


# =========================================================
# Read
# =========================================================

def get_career_job_details(
    career_job_id: int,
):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM career_job_details

            WHERE career_job_id = ?
            """,
            (career_job_id,),
        )

        row = cursor.fetchone()

    if row is None:
        return None

    return _deserialize(row)


def get_all_career_job_details():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM career_job_details

            ORDER BY validated_at DESC
            """
        )

        rows = cursor.fetchall()

    return [
        _deserialize(row)
        for row in rows
    ]


def get_new_career_job_details():
    """Return validated career jobs still awaiting manual review."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                career_job_id,
                source_url,
                title,
                company,
                level,
                validated_at
            FROM career_job_details
            WHERE job_status = 'NEW'
            ORDER BY validated_at ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# Update
# =========================================================

def update_career_job_status(
    career_job_id: int,
    status: str,
):

    if status not in JOB_STATUS:
        raise ValueError(
            f"Invalid job status: {status}"
        )

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE career_job_details

            SET job_status = ?

            WHERE career_job_id = ?
            """,
            (
                status,
                career_job_id,
            ),
        )

        conn.commit()


def update_career_job_ai_status(
    career_job_id: int,
    status: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE career_job_details

            SET ai_status = ?

            WHERE career_job_id = ?
            """,
            (
                status,
                career_job_id,
            ),
        )

        conn.commit()


# =========================================================
# Delete
# =========================================================

def delete_career_job_details(
    career_job_id: int,
):

    with get_connection() as conn:

        conn.execute(
            """
            DELETE FROM career_job_details

            WHERE career_job_id = ?
            """,
            (career_job_id,),
        )

        conn.commit()


# =========================================================
# Helpers
# =========================================================

def _deserialize(row):

    data = dict(row)

    for field in (
        "technologies",
        "requirements",
        "differentials",
        "benefits",
    ):

        value = data.get(field)

        if value:
            data[field] = json.loads(value)
        else:
            data[field] = []

    return data