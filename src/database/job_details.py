import json

from database.database import get_connection


# =========================================================
# Constants
# =========================================================

DEFAULT_JOB_STATUS = "NEW"

JOB_STATUSES = {
    "NEW",
    "INTERESTED",
    "APPLIED",
    "INTERVIEW",
    "REJECTED",
    "ACCEPTED",
    "DISCARDED",
}


# =========================================================
# Create
# =========================================================

def insert_job_details(job_id: int, details: dict) -> int:
    """
    Saves validated job details collected by Playwright.
    """

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO job_details (

                job_id,

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

                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?

            )
            """,
            (
                job_id,

                int(details.get("page_not_found", False)),

                details.get("published_date"),

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

                json.dumps(
                    details.get("technologies", []),
                    ensure_ascii=False,
                ),

                json.dumps(
                    details.get("requirements", []),
                    ensure_ascii=False,
                ),

                json.dumps(
                    details.get("differentials", []),
                    ensure_ascii=False,
                ),

                json.dumps(
                    details.get("benefits", []),
                    ensure_ascii=False,
                ),

                DEFAULT_JOB_STATUS,

                "PENDING",
            ),
        )

        conn.commit()

        return cursor.lastrowid


# =========================================================
# Exists
# =========================================================

def job_details_exists(job_id: int) -> bool:

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT 1

            FROM job_details

            WHERE job_id = ?
            """,
            (job_id,),
        )

        return cursor.fetchone() is not None


# =========================================================
# Read
# =========================================================

def get_job_details(job_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM job_details

            WHERE job_id = ?
            """,
            (job_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return _deserialize(row)


def get_pending_ai_jobs():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT

                j.id,
                j.telegram_hash,
                j.link,
                j.created_at,

                jd.*

            FROM job_details jd

            INNER JOIN jobs j
                ON j.id = jd.job_id

            WHERE

                jd.ai_status = 'PENDING'

                AND jd.page_not_found = 0

            ORDER BY

                jd.validated_at
            """
        )

        return [_deserialize(row) for row in cursor.fetchall()]


def get_all_job_details():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM job_details

            ORDER BY validated_at DESC
            """
        )

        return [_deserialize(row) for row in cursor.fetchall()


]


# =========================================================
# Update
# =========================================================

def update_ai_status(
    job_id: int,
    status: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE job_details

            SET ai_status = ?

            WHERE job_id = ?
            """,
            (
                status,
                job_id,
            ),
        )

        conn.commit()


def update_job_status(
    job_id: int,
    status: str,
):

    if status not in JOB_STATUSES:
        raise ValueError(f"Invalid job status: {status}")

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE job_details

            SET job_status = ?

            WHERE job_id = ?
            """,
            (
                status,
                job_id,
            ),
        )

        conn.commit()


# =========================================================
# Delete
# =========================================================

def delete_job_details(job_id: int):

    with get_connection() as conn:

        conn.execute(
            """
            DELETE FROM job_details

            WHERE job_id = ?
            """,
            (job_id,),
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