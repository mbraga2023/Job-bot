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

                source,

                description,

                technologies,
                requirements,
                differentials,
                benefits,

                apply_button

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,

                int(details["page_not_found"]),

                details["published_date"],

                details["title"],
                details["company"],
                details["location"],

                int(details["remote"]),

                details["level"],
                details["contract"],

                details["source"],

                details["description"],

                json.dumps(details["technologies"], ensure_ascii=False),
                json.dumps(details["requirements"], ensure_ascii=False),
                json.dumps(details["differentials"], ensure_ascii=False),
                json.dumps(details["benefits"], ensure_ascii=False),

                int(details["apply_button"]),
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