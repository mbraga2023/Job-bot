from database.database import get_connection


# =========================================================
# Create
# =========================================================

def insert_analysis(analysis: dict) -> int:
    """
    Saves an AI analysis.

    Returns:
        Analysis ID.
    """

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO job_ai_analysis (

                job_id,

                model,

                ai_score,

                recommendation,

                summary,

                strengths,

                weaknesses,

                matching_skills,

                missing_skills,

                prompt_version

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis["job_id"],

                analysis["model"],

                analysis["ai_score"],

                analysis["recommendation"],

                analysis["summary"],

                analysis["strengths"],

                analysis["weaknesses"],

                analysis["matching_skills"],

                analysis["missing_skills"],

                analysis["prompt_version"],
            ),
        )

        conn.commit()

        return cursor.lastrowid


# =========================================================
# Read
# =========================================================

def get_analysis(analysis_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM job_ai_analysis

            WHERE id = ?
            """,
            (analysis_id,),
        )

        return cursor.fetchone()


def get_latest_analysis(job_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM job_ai_analysis

            WHERE job_id = ?

            ORDER BY created_at DESC

            LIMIT 1
            """,
            (job_id,),
        )

        return cursor.fetchone()


def get_analysis_history(job_id: int):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM job_ai_analysis

            WHERE job_id = ?

            ORDER BY created_at DESC
            """,
            (job_id,),
        )

        return cursor.fetchall()


def get_all_analysis():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT *

            FROM job_ai_analysis

            ORDER BY created_at DESC
            """
        )

        return cursor.fetchall()


# =========================================================
# Update
# =========================================================

def update_recommendation(
    analysis_id: int,
    recommendation: str,
):

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE job_ai_analysis

            SET recommendation = ?

            WHERE id = ?
            """,
            (
                recommendation,
                analysis_id,
            ),
        )

        conn.commit()


# =========================================================
# Delete
# =========================================================

def delete_analysis(analysis_id: int):

    with get_connection() as conn:

        conn.execute(
            """
            DELETE

            FROM job_ai_analysis

            WHERE id = ?
            """,
            (analysis_id,),
        )

        conn.commit()