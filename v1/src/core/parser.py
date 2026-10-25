# parser.py

import html
import re


# =========================================================
# Constants
# =========================================================

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


# =========================================================
# Helpers
# =========================================================

def clean(value: str) -> str:

    if not value:
        return ""

    value = html.unescape(value)

    # Markdown links
    value = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r"\1",
        value,
    )

    # Telegram markdown
    value = re.sub(
        r"[*_`#]",
        "",
        value,
    )

    # Collapse whitespace
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_message(text: str) -> str:
    """
    Removes decorative emojis before labels.

    🏢Empresa:
    🌍Local:
    📄Contrato:
    👨‍💻Atuação:
    🎓Nível:
    """

    text = html.unescape(text)

    for label in FIELD_LABELS:

        text = re.sub(
            rf"[^\w\s]*\s*{label}\s*:",
            f"{label}:",
            text,
            flags=re.IGNORECASE,
        )

    return text


def extract(label: str, text: str) -> str:

    next_labels = "|".join(STOP_LABELS)

    pattern = (
        rf"{label}\s*:\s*(.*?)"
        rf"(?=(?:{next_labels})\s*:|$)"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return ""

    return clean(match.group(1))


def clean_level(value: str) -> str:

    value = clean(value)

    stop_words = (
        "verificada",
        "candidatura",
        "linkedin",
        "indeed",
        "gupy",
        "❤️",
        "✨",
        "🚀",
    )

    lower = value.lower()

    for word in stop_words:

        idx = lower.find(word)

        if idx != -1:
            value = value[:idx]
            lower = value.lower()

    return value.strip()


def clean_location(value: str) -> str:

    value = clean(value)

    stop_words = (
        "recrutador",
        "perfil",
    )

    lower = value.lower()

    for word in stop_words:

        idx = lower.find(word)

        if idx != -1:
            value = value[:idx]
            lower = value.lower()

    return value.strip()


# =========================================================
# Public
# =========================================================

def parse_job(text: str):

    text = normalize_message(text)

    return {

        "title": extract("Título", text),

        "company": extract("Empresa", text),

        "location": clean_location(
            extract("Local", text)
        ),

        "work_model": extract("Atuação", text),

        "contract": extract("Contrato", text),

        "level": clean_level(
            extract("Nível", text)
        ),

        "description": clean(text),

    }