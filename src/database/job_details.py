import json

from database.database import get_connection


# =========================================================
# Create
# =========================================================

def insert_job_details(job_id: int, details: dict) -> int:
    """
    Saves Playwright analysis for a job.

    Returns:
        job_details ID.
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
                benefits
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                job_id,
                int(bool(details.get("page_not_found", False))),
                details.get("published_date") or "",
                details.get("title") or "",
                details.get("company") or "",
                details.get("location") or "",
                int(bool(details.get("remote", False))),
                details.get("level") or "",
                details.get("contract") or "",
                details.get("job_source") or "",
                details.get("application_url") or "",
                details.get("application_source") or "",
                details.get("description") or "",
                json.dumps(details.get("technologies", []), ensure_ascii=False),
                json.dumps(details.get("requirements", []), ensure_ascii=False),
                json.dumps(details.get("differentials", []), ensure_ascii=False),
                json.dumps(details.get("benefits", []), ensure_ascii=False),
            ),
        )

        conn.commit()

        return cursor.lastrowid


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
                j.*,
                jd.*

            FROM job_details jd

            INNER JOIN jobs j
                ON j.id = jd.job_id

            WHERE jd.ai_status = 'PENDING'
              AND jd.page_not_found = 0

            ORDER BY jd.validated_at
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

        return [_deserialize(row) for row in cursor.fetchall()]


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