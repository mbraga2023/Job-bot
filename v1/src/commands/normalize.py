"""Stage 3.1 entry point for normalization."""

from core.parser import parse_job


def normalize_job(raw_text: str):
    return parse_job(raw_text)


def run(raw_text: str | None = None):
    if raw_text is None:
        print("Stage 3.1 - normalization uses core.parser.parse_job().")
        return None
    return normalize_job(raw_text)


if __name__ == "__main__":
    run()
