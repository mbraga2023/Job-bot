#database.py
import sqlite3
from pathlib import Path

# ---------------------------------------------------------
# Database configuration
# ---------------------------------------------------------

DB_FOLDER = Path("database")
DB_FOLDER.mkdir(exist_ok=True)

DB_PATH = DB_FOLDER / "jobs.db"


# ---------------------------------------------------------
# Connection
# ---------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Returns a SQLite connection with Row factory enabled.

    Example:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM jobs").fetchall()

        row["title"]
        row["company"]
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn