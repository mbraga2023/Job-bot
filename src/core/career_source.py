SOURCE_TYPES = {
    "UNKNOWN",
    "GENERIC",
    "GUPY",
    "PANDAPE",
    "QUICKIN",
    "KENOBY",
    "VAGAS",
    "ENTER",
    "LINKEDIN",
}


def normalize_source_type(
    source_type: str | None,
) -> str:

    if not source_type:
        return "UNKNOWN"

    normalized = source_type.strip().upper()

    if normalized not in SOURCE_TYPES:
        return "UNKNOWN"

    return normalized