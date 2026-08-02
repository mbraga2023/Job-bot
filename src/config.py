from pathlib import Path

HEADLESS = True
MAX_JOBS = 20
OUTPUT_FOLDER = Path("output")
DATABASE = Path("database/jobs.db")

OPENAI_MODEL = "gpt-5.5"
RELEVANCE_THRESHOLD = 80

TIMEOUT = 30000