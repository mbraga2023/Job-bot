"""Telegram Message Parsing Utilities for v2."""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any

FIELD_LABELS = (
    "Título",
    "Empresa",
    "Local",
    "Atuação",
    "Contrato",
    "Nível",
)

STOP_LABELS = (
    "Título",
    "Empresa",
    "Local",
    "Atuação",
    "Contrato",
    "Nível",
    "Recrutador",
)


def clean(value: str) -> str:
    """Clean markdown links, telegram markup, and extra whitespaces."""
    if not value:
        return ""
    value = html.unescape(value)
    # Strip markdown links [text](url) -> text
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", value)
    # Strip markdown symbols
    value = re.sub(r"[*_`#]", "", value)
    # Collapse whitespace
    return " ".join(value.split()).strip()


def normalize_message(text: str) -> str:
    """Remove emojis and decorative icons before labels."""
    text = html.unescape(text)
    for label in FIELD_LABELS:
        text = re.sub(
            rf"[^\w\s]*\s*{label}\s*:",
            f"{label}:",
            text,
            flags=re.IGNORECASE,
        )
    return text


def extract_field(label: str, text: str) -> str:
    """Extract a labeled field from normalized Telegram message text."""
    next_labels = "|".join(STOP_LABELS)
    pattern = rf"{label}\s*:\s*(.*?)(?=(?:{next_labels})\s*:|$)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return clean(match.group(1))


def clean_level(value: str) -> str:
    """Clean level string of trailing emojis or keywords."""
    value = clean(value)
    stop_words = ("verificada", "candidatura", "linkedin", "indeed", "gupy", "❤️", "✨", "🚀")
    lower = value.lower()
    for word in stop_words:
        idx = lower.find(word)
        if idx != -1:
            value = value[:idx]
            lower = value.lower()
    return value.strip()


def clean_location(value: str) -> str:
    """Clean location string of trailing recruiter metadata."""
    value = clean(value)
    stop_words = ("recrutador", "perfil")
    lower = value.lower()
    for word in stop_words:
        idx = lower.find(word)
        if idx != -1:
            value = value[:idx]
            lower = value.lower()
    return value.strip()


def parse_job_message(text: str) -> dict[str, Any]:
    """Parse a structured Telegram job posting into dictionary."""
    normalized = normalize_message(text)
    return {
        "title": extract_field("Título", normalized),
        "company": extract_field("Empresa", normalized),
        "location": clean_location(extract_field("Local", normalized)),
        "work_model": extract_field("Atuação", normalized),
        "contract": extract_field("Contrato", normalized),
        "level": clean_level(extract_field("Nível", normalized)),
        "description": clean(normalized),
    }


def extract_message_link(message: Any) -> str | None:
    """Extract first valid HTTP(S) URL from Telethon message."""
    text = getattr(message, "text", "") or ""

    # 1. Direct URLs in text
    urls = re.findall(r"https?://[^\s)]+", text)
    if urls:
        return urls[0].rstrip(".,]")

    # 2. Hidden entity links
    entities = getattr(message, "entities", None) or []
    for entity in entities:
        url = getattr(entity, "url", None)
        if url:
            return url

    # 3. Inline keyboard buttons
    reply_markup = getattr(message, "reply_markup", None)
    if reply_markup and hasattr(reply_markup, "rows"):
        for row in reply_markup.rows:
            for button in getattr(row, "buttons", []):
                url = getattr(button, "url", None)
                if url:
                    return url

    return None


def is_remote_job(job_data: dict[str, Any]) -> int:
    """Check if job description or location describes remote work."""
    text = " ".join(str(v) for v in job_data.values() if v).lower()
    not_remote_keywords = (
        "on-site",
        "on site",
        "onsite",
        "presencial",
        "hybrid",
        "híbrido",
        "hibrido",
    )
    if any(keyword in text for keyword in not_remote_keywords):
        return 0

    keywords = ("remoto", "remota", "remote", "home office", "home-office", "100% remoto")
    return 1 if any(kw in text for kw in keywords) else 0


def generate_telegram_hash(text: str) -> str:
    """Compute MD5 hash of raw Telegram text."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()
