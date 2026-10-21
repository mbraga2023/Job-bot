"""Unified Date Utilities for v2.

Handles:
- Parsing various date formats (ISO, Portuguese textual dates, standard numeric formats).
- Relative dates ("há 2 dias", "3 days ago", "ontem", "hoje").
- Normalizing dates to ISO-8601 (YYYY-MM-DD).
- Staleness checking (e.g. > 30 days old).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

PORTUGUESE_MONTHS: dict[str, int] = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

COMMON_FORMATS: tuple[str, ...] = (
    "%m/%d/%y",
    "%m/%d/%Y",
    "%m-%d-%y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%A, %B %d, %Y",
    "%A, %b %d, %Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)


def parse_relative_date(text: str, now: datetime | None = None) -> date | None:
    """Parse relative time expressions (e.g., 'há 2 dias', '3 days ago', 'ontem')."""
    lower = text.lower().strip()
    ref = now or datetime.now(timezone.utc)

    if lower in ("hoje", "today", "agora", "just now"):
        return ref.date()

    if lower in ("ontem", "yesterday"):
        return (ref - timedelta(days=1)).date()

    # "há X dias" or "X days ago"
    days_match = re.search(r"(?:h[aá]\s+)?(\d+)\s*(?:dia|dias|day|days)(?:\s+atr[aá]s|\s+ago)?", lower)
    if days_match:
        days = int(days_match.group(1))
        return (ref - timedelta(days=days)).date()

    # "há X semanas" or "X weeks ago"
    weeks_match = re.search(r"(?:h[aá]\s+)?(\d+)\s*(?:semana|semanas|week|weeks)(?:\s+atr[aá]s|\s+ago)?", lower)
    if weeks_match:
        weeks = int(weeks_match.group(1))
        return (ref - timedelta(days=weeks * 7)).date()

    # "há X meses" or "X months ago"
    months_match = re.search(r"(?:h[aá]\s+)?(\d+)\s*(?:m[eê]s|meses|month|months)(?:\s+atr[aá]s|\s+ago)?", lower)
    if months_match:
        months = int(months_match.group(1))
        return (ref - timedelta(days=months * 30)).date()

    # "há X horas"
    if re.search(r"(?:h[aá]\s+)?\d+\s*(?:hora|horas|hour|hours)", lower):
        return ref.date()

    return None


def normalize_published_date(value: str | None, now: datetime | None = None) -> str | None:
    """Normalize any date representation to an ISO date string (YYYY-MM-DD)."""
    if not value or not str(value).strip():
        return None

    cleaned = str(value).strip()
    cleaned = re.sub(
        r"\s*\((?:updated|atualizad[oa])\b[^)]*\)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Check relative dates first
    rel = parse_relative_date(cleaned, now=now)
    if rel:
        return rel.isoformat()

    # Check ISO formats (with or without Z/offset)
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass

    # Check Portuguese textual format: '18 de outubro de 2026'
    pt_match = re.fullmatch(
        r"(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})",
        cleaned,
        flags=re.IGNORECASE,
    )
    if pt_match:
        day, month_name, year = pt_match.groups()
        month = PORTUGUESE_MONTHS.get(month_name.casefold())
        if month:
            try:
                return date(int(year), month, int(day)).isoformat()
            except ValueError:
                return None

    # Check common date formats
    for fmt in COMMON_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def is_older_than_days(
    date_str: str | None,
    days: int = 30,
    now: datetime | None = None,
) -> bool:
    """Check if date string is older than the specified number of days."""
    if not date_str:
        return False

    ref = now or datetime.now(timezone.utc)
    target_date: date | None = None

    try:
        target_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00")).date()
    except ValueError:
        pass

    if not target_date:
        normalized = normalize_published_date(date_str, now=ref)
        if normalized:
            try:
                target_date = date.fromisoformat(normalized)
            except ValueError:
                return False

    if not target_date:
        return False

    return (ref.date() - target_date) > timedelta(days=days)
