from database.database import get_connection


# =========================================================
# Public
# =========================================================

def create_database():
    """Create all database tables."""

    create_jobs_table()
    create_job_details_table()
    create_job_ai_analysis_table()
    create_resume_matches_table()
    create_applications_table()


# =========================================================
# jobs
# =========================================================

def create_jobs_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            telegram_hash TEXT NOT NULL UNIQUE,

            title TEXT,
            company TEXT,
            location TEXT,
            contract TEXT,
            level TEXT,

            link TEXT NOT NULL,

            category TEXT,

            remote INTEGER DEFAULT 0,

            score INTEGER DEFAULT 0,

            applied INTEGER DEFAULT 0,

            notes TEXT,

            validation_status TEXT NOT NULL DEFAULT 'PENDING',

            validated_at DATETIME,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP

        )
        """)

        conn.commit()


# =========================================================
# job_details
# =========================================================

def create_job_details_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS job_details (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            job_id INTEGER NOT NULL UNIQUE,

            page_not_found INTEGER DEFAULT 0,

            published_date TEXT,

            title TEXT,
            company TEXT,
            location TEXT,

            remote INTEGER DEFAULT 0,

            level TEXT,
            contract TEXT,

            source TEXT,

            description TEXT,

            technologies TEXT,
            requirements TEXT,
            differentials TEXT,
            benefits TEXT,

            apply_button INTEGER DEFAULT 0,

            ai_status TEXT NOT NULL DEFAULT 'PENDING',

            validated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(job_id)
                REFERENCES jobs(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()


# =========================================================
# job_ai_analysis
# =========================================================

def create_job_ai_analysis_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS job_ai_analysis (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            job_id INTEGER NOT NULL,

            model TEXT,

            ai_score INTEGER,

            recommendation TEXT,

            summary TEXT,

            strengths TEXT,

            weaknesses TEXT,

            matching_skills TEXT,

            missing_skills TEXT,

            prompt_version TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(job_id)
                REFERENCES jobs(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()


# =========================================================
# resume_matches
# =========================================================

def create_resume_matches_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS resume_matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            job_id INTEGER NOT NULL,

            resume_name TEXT,

            match_score INTEGER,

            matched_skills TEXT,

            missing_skills TEXT,

            recommendation TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(job_id)
                REFERENCES jobs(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()


# =========================================================
# applications
# =========================================================

def create_applications_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            job_id INTEGER NOT NULL,

            applied_at DATETIME,

            status TEXT,

            notes TEXT,

            follow_up_date DATETIME,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(job_id)
                REFERENCES jobs(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()