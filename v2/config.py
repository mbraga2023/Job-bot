"""v2 Configuration Module.

Decoupled configuration with lazy-loading for pipeline-specific settings.
Career flow will not fail if Telegram environment variables are not set.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load root .env file
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def get_env(name: str, default: str | None = None, cast=None):
    """Retrieve an environment variable with optional default and casting."""
    value = os.getenv(name)
    if value is None or value == "":
        return default

    if cast is not None:
        try:
            return cast(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Invalid value for environment variable {name}: {value!r}"
            ) from exc

    return value


def require_env(name: str, cast=None):
    """Retrieve an environment variable or raise an error if not found."""
    value = get_env(name, cast=cast)
    if value is None:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in your shell or .env file before running this flow."
        )
    return value


class TelegramConfig:
    """Lazy configuration for Telegram pipeline."""

    @property
    def api_id(self) -> int:
        return require_env("API_ID", cast=int)

    @property
    def api_hash(self) -> str:
        return require_env("API_HASH")

    @property
    def channel(self) -> str:
        return require_env("TELEGRAM_CHANNEL")

    @property
    def session_name(self) -> str:
        return get_env("TELEGRAM_SESSION", default="job_bot_session")


class AppConfig:
    """Global configuration settings for v2."""

    # Paths
    root_dir: Path = ROOT_DIR
    v2_dir: Path = ROOT_DIR / "v2"
    db_path: Path = ROOT_DIR / "database" / "jobs_v2.db"
    v1_db_path: Path = ROOT_DIR / "database" / "jobs.db"
    storage_dir: Path = ROOT_DIR / "storage"
    linkedin_profile_dir: Path = ROOT_DIR / "storage" / "linkedin_profile"
    meupadrinho_profile_dir: Path = ROOT_DIR / "storage" / "meupadrinho_edge_profile"
    output_dir: Path = ROOT_DIR / "output"

    # Browser & Scraping
    headless: bool = get_env("HEADLESS", default="true").lower() in ("true", "1", "yes")
    timeout_ms: int = get_env("TIMEOUT", default=30000, cast=int)
    validate_delay_min: float = get_env("VALIDATE_DELAY_MIN", default=2.5, cast=float)
    validate_delay_max: float = get_env("VALIDATE_DELAY_MAX", default=5.0, cast=float)
    validation_limit: int = get_env("VALIDATION_LIMIT", default=500, cast=int)

    # Local LLM
    ollama_model: str = get_env("OLLAMA_MODEL", default="qwen2.5-coder:1.5b")

    # Flow configs
    telegram: TelegramConfig = TelegramConfig()


config = AppConfig()
