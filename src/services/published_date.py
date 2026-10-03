import re
from datetime import date, datetime


PORTUGUESE_MONTHS = {
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


def normalize_published_date(value: str | None) -> str | None:
    if not value or not value.strip():
        return None

    value = value.strip()
    value = re.sub(
        r"\s*\((?:updated|atualizad[oa])\b[^)]*\)\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date().isoformat()
    except ValueError:
        pass

    portuguese_date = re.fullmatch(
        r"(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})",
        value,
        flags=re.IGNORECASE,
    )
    if portuguese_date:
        day, month_name, year = portuguese_date.groups()
        month = PORTUGUESE_MONTHS.get(month_name.casefold())
        if month:
            try:
                return date(int(year), month, int(day)).isoformat()
            except ValueError:
                return None

    formats = (
        "%m/%d/%y",
        "%m/%d/%Y",
        "%m-%d-%y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%A, %B %d, %Y",
        "%A, %b %d, %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    )

    for date_format in formats:
        try:
            return datetime.strptime(
                value,
                date_format,
            ).date().isoformat()
        except ValueError:
            continue

    return None