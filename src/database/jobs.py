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

def insert_job(job: dict) -> int:
    """
    Inserts a new job.

    Returns:
        Job ID.
    """

    with get_connection() as conn:

        cursor = conn.execute(
            """
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

                score,

                status

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["telegram_hash"],

                job["title"],
                job["company"],
                job["location"],
                job["contract"],
                job["level"],

                job["link"],

                job["category"],

                int(job["remote"]),

                job["score"],

                DEFAULT_JOB_STATUS,
            ),
        )

        conn.commit()

        return cursor.lastrowid


# =========================================================
# Exists
# =========================================================

def job_exists(telegram_hash: str) -> bool:

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT 1

            FROM jobs

            WHERE telegram_hash = ?

            """,
            (telegram_hash,),
        )

        return cursor.fetchone() is not None


# =========================================================
# Read
# =========================================================

def get_job(job_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM jobs

            WHERE id = ?

            """,
            (job_id,),
        )

        return cursor.fetchone()



def get_first_job():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM jobs

            ORDER BY score DESC,
                     created_at DESC

            LIMIT 1

            """
        )

        return cursor.fetchone()



def get_all_jobs():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT
    id,
    score,
    category,
    remote,
    status,
    title,
    company,
    location,
    contract,
    level,
    link,
    created_at
FROM jobs
ORDER BY score DESC,
         created_at DESC;

            """
        )

        return cursor.fetchall()



def get_jobs_by_job_status(status: str):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM jobs

            WHERE status = ?

            ORDER BY score DESC,
                     created_at DESC

            """,
            (status,),
        )

        return cursor.fetchall()



def get_jobs_by_validation_status(status: str):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM jobs

            WHERE validation_status = ?

            ORDER BY score DESC,
                     created_at DESC

            """,
            (status,),
        )

        return cursor.fetchall()



def get_meupadrinho_jobs(limit: int = 30):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT
                j.*

            FROM jobs j

            LEFT JOIN job_details jd
                ON jd.job_id = j.id

            WHERE j.link LIKE '%meupadrinho%'
              AND j.validation_status = 'PENDING'
              AND jd.job_id IS NULL

            ORDER BY
                j.created_at DESC,
                j.remote DESC,
                j.score DESC

            LIMIT ?
            """,
            (limit,),
        )

        return cursor.fetchall()



# =========================================================
# Statistics
# =========================================================

def get_statistics():

    with get_connection() as conn:

        total = conn.execute(
            """
            SELECT COUNT(*)

            FROM jobs
            """
        ).fetchone()[0]


        qa = conn.execute(
            """
            SELECT COUNT(*)

            FROM jobs

            WHERE category='QA'

            """
        ).fetchone()[0]


        remote = conn.execute(
            """
            SELECT COUNT(*)

            FROM jobs

            WHERE remote=1

            """
        ).fetchone()[0]


        applied = conn.execute(
            """
            SELECT COUNT(*)

            FROM jobs

            WHERE status='APPLIED'

            """
        ).fetchone()[0]


        interviews = conn.execute(
            """
            SELECT COUNT(*)

            FROM jobs

            WHERE status='INTERVIEW'

            """
        ).fetchone()[0]


    return {

        "total": total,

        "qa": qa,

        "remote": remote,

        "applied": applied,

        "interviews": interviews,

    }


# =========================================================
# Update
# =========================================================

def update_validation_status(
    job_id: int,
    status: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE jobs

            SET

                validation_status = ?,

                validated_at = CURRENT_TIMESTAMP


            WHERE id = ?

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
        raise ValueError(
            f"Invalid job status: {status}"
        )


    with get_connection() as conn:

        conn.execute(
            """
            UPDATE jobs

            SET status = ?

            WHERE id = ?

            """,
            (
                status,

                job_id,
            ),
        )

        conn.commit()



def update_notes(
    job_id: int,
    notes: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE jobs

            SET notes = ?

            WHERE id = ?

            """,
            (
                notes,

                job_id,
            ),
        )

        conn.commit()



# =========================================================
# Delete
# =========================================================

def delete_job(job_id: int):

    with get_connection() as conn:

        conn.execute(
            """
            DELETE FROM jobs

            WHERE id = ?

            """,
            (job_id,),
        )

        conn.commit()