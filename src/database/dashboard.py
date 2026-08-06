from database.database import get_connection


def get_dashboard_jobs():
    with get_connection() as conn:
        conn.row_factory = __import__("sqlite3").Row

        cursor = conn.execute(
            """
            SELECT
                jd.job_id AS id,
                j.category,
                jd.remote,
                jd.title,
                jd.company,
                jd.location,
                jd.level,
                jd.contract,
                jd.job_source,
                jd.application_url,
                jd.application_source,
                jd.description,
                jd.technologies,
                jd.requirements,
                jd.differentials,
                jd.benefits,
                jd.job_status,
                jd.ai_status,
                jd.validated_at,
                jd.page_not_found,
                jd.published_date,
                j.link

            FROM job_details AS jd
            JOIN jobs AS j
                ON j.id = jd.job_id

            ORDER BY
                jd.published_date ASC NULLS LAST,
                jd.validated_at DESC
            """
        )

        return cursor.fetchall()

def get_job_statuses():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT DISTINCT job_status

            FROM job_details

            WHERE job_status IS NOT NULL

            ORDER BY job_status
            """
        )

        return [row[0] for row in cursor.fetchall()]