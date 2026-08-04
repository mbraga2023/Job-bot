from database.database import get_connection
def get_dashboard_jobs():

    with get_connection() as conn:

        cursor = conn.execute(
            """
            SELECT

                j.id,

                j.score,
                j.category,
                j.remote,

                j.title,
                j.company,
                j.location,

                j.level,

                j.status,

                j.link,

                j.created_at,


                jd.page_not_found,

                jd.published_date,

                jd.description,


                jd.technologies,

                jd.requirements


            FROM jobs j


            LEFT JOIN job_details jd

                ON jd.job_id = j.id


            WHERE j.remote = 1 AND j.level IN ('Pleno', 'Junior', '')


            ORDER BY

                jd.published_date ASC NULLS LAST,

                j.score DESC

            """
        )


        return cursor.fetchall()