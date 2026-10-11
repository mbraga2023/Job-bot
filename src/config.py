#config.py
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()


def require_env(name: str, cast=None):
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in your shell or .env file before running the app."
        )

    if cast is None:
        return value

    try:
        return cast(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid value for {name}: {value!r}"
        ) from exc


API_ID = require_env("API_ID", int)
API_HASH = require_env("API_HASH")
TELEGRAM_CHANNEL = require_env("TELEGRAM_CHANNEL")

HEADLESS = True
VALIDATION_LIMIT = 50
MAX_JOBS = VALIDATION_LIMIT
OUTPUT_FOLDER = Path("output")
DATABASE = Path("database/jobs.db")

OPENAI_MODEL = "gpt-5.5"
RELEVANCE_THRESHOLD = 80

TIMEOUT = 30000

# Delay between page requests during validation (seconds) to prevent rate limits
VALIDATE_DELAY_MIN = 2.5
VALIDATE_DELAY_MAX = 5.0
