from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")

HEADLESS = True
MAX_JOBS = 20
OUTPUT_FOLDER = Path("output")
DATABASE = Path("database/jobs.db")

OPENAI_MODEL = "gpt-5.5"
RELEVANCE_THRESHOLD = 80

TIMEOUT = 30000
