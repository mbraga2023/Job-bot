from database.database import get_connection
from database.career_sources import create_career_sources_table
from database.career_jobs import create_career_jobs_table


# =========================================================
# Public
# =========================================================

def create_database():
    """Create all database tables."""

    create_jobs_table()
    create_job_details_table()
    create_job_ai_analysis_table()
    create_resume_matches_table()


# =========================================================
# jobs (Stage 1 - Raw Telegram Data)
# =========================================================

def create_jobs_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            telegram_hash TEXT NOT NULL,

            title TEXT,
            company TEXT,
            location TEXT,
            contract TEXT,
            level TEXT,

            link TEXT NOT NULL UNIQUE,

            category TEXT,

            remote INTEGER DEFAULT 0,

            validation_status TEXT NOT NULL DEFAULT 'PENDING',

            validated_at DATETIME,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP

        )
        """)

        conn.commit()


# =========================================================
# job_details (Stage 2 - Validated Job)
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

            job_source TEXT,

            application_url TEXT,

            application_source TEXT,

            description TEXT,

            technologies TEXT,

            requirements TEXT,

            differentials TEXT,

            benefits TEXT,

            job_status TEXT NOT NULL DEFAULT 'NEW',

            ai_status TEXT NOT NULL DEFAULT 'PENDING',

            validated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(job_id)
                REFERENCES jobs(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()


# =========================================================
# job_ai_analysis (Stage 3 - AI Analysis)
# =========================================================

def create_job_ai_analysis_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS job_ai_analysis (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            job_id INTEGER NOT NULL UNIQUE,

            model TEXT,

            ai_score INTEGER,

            recommendation TEXT,

            summary TEXT,

            strengths TEXT,

            weaknesses TEXT,

            matching_skills TEXT,

            missing_skills TEXT,

            prompt_version TEXT,

            analysis_version INTEGER DEFAULT 1,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(job_id)
                REFERENCES jobs(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()


# =========================================================
# resume_matches (Stage 4 - Resume Matching)
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
        
def create_database():
    """Create all database tables."""

    create_jobs_table()
    create_job_details_table()
    create_job_ai_analysis_table()
    create_resume_matches_table()

    create_career_sources_table()
    create_career_jobs_table()

# =========================================================
# career_sources (Stage 1.2 - Career Sources)
# =========================================================

def create_career_sources_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS career_sources (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            company TEXT NOT NULL,

            careers_url TEXT NOT NULL UNIQUE,

            source_type TEXT DEFAULT 'UNKNOWN',

            api_url TEXT,

            api_method TEXT,

            api_config TEXT,

            active INTEGER DEFAULT 1,

            last_checked_at DATETIME,

            last_success_at DATETIME,

            last_error TEXT,

            discovered_jobs INTEGER DEFAULT 0,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP

        )
        """)

        conn.commit()


# =========================================================
# career_jobs (Stage 1.2 - Discovered Career Jobs)
# =========================================================

def create_career_jobs_table():

    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS career_jobs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            career_source_id INTEGER NOT NULL,

            external_id TEXT,

            title TEXT,

            company TEXT,

            location TEXT,

            url TEXT NOT NULL,

            published_date TEXT,

            raw_data TEXT,

            first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            active INTEGER DEFAULT 1,

            UNIQUE(career_source_id, url),

            FOREIGN KEY(career_source_id)
                REFERENCES career_sources(id)
                ON DELETE CASCADE

        )
        """)

        conn.commit()