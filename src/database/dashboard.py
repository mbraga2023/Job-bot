from database.database import get_connection


def get_dashboard_jobs():
    with get_connection() as conn:
        conn.row_factory = __import__("sqlite3").Row

        cursor = conn.execute(
            """
            SELECT
                j.id,
                j.category,
                j.remote AS job_remote,
                j.title AS job_title,
                j.company AS job_company,
                j.location AS job_location,
                j.level AS job_level,
                j.validation_status AS legacy_status,
                j.link,
                j.created_at,

                jd.job_id,
                jd.page_not_found,
                jd.published_date,
                jd.title,
                jd.company,
                jd.location,
                jd.remote,
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
                jd.validated_at

            FROM jobs AS j
            LEFT JOIN job_details AS jd
                ON jd.job_id = j.id

            WHERE COALESCE(jd.remote, j.remote, 0) = 1
              AND COALESCE(jd.level, j.level, '') IN ('Pleno', 'Junior', '')

            ORDER BY
                jd.published_date ASC NULLS LAST,
                j.created_at DESC
            """
        )

        return cursor.fetchall()
