from database.database import get_connection


# =========================================================
# Create
# =========================================================

def insert_application(
    job_id: int,
    status: str = "APPLIED",
    notes: str | None = None,
    applied_at: str | None = None,
    follow_up_date: str | None = None,
) -> int:
    """
    Creates a new application record.

    Returns:
        Application ID.
    """

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO applications (

                job_id,
                applied_at,
                status,
                notes,
                follow_up_date

            )

            VALUES (?, ?, ?, ?, ?)
            """,
            (
                job_id,
                applied_at,
                status,
                notes,
                follow_up_date,
            ),
        )

        conn.commit()

        return cursor.lastrowid


# =========================================================
# Read
# =========================================================

def get_application(application_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        )

        return cursor.fetchone()


def get_application_by_job(job_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *
            FROM applications
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (job_id,),
        )

        return cursor.fetchone()


def get_all_applications():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *
            FROM applications
            ORDER BY created_at DESC
            """
        )

        return cursor.fetchall()


def get_pending_followups():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *
            FROM applications
            WHERE follow_up_date IS NOT NULL
              AND status != 'REJECTED'
              AND status != 'HIRED'
            ORDER BY follow_up_date
            """
        )

        return cursor.fetchall()


# =========================================================
# Update
# =========================================================

def update_application_status(
    application_id: int,
    status: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE applications
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                application_id,
            ),
        )

        conn.commit()


def update_application_notes(
    application_id: int,
    notes: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE applications
            SET notes = ?
            WHERE id = ?
            """,
            (
                notes,
                application_id,
            ),
        )

        conn.commit()


def update_follow_up_date(
    application_id: int,
    follow_up_date: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE applications
            SET follow_up_date = ?
            WHERE id = ?
            """,
            (
                follow_up_date,
                application_id,
            ),
        )

        conn.commit()


# =========================================================
# Delete
# =========================================================

def delete_application(application_id: int):

    with get_connection() as conn:

        conn.execute(
            """
            DELETE FROM applications
            WHERE id = ?
            """,
            (application_id,),
        )

        conn.commit()