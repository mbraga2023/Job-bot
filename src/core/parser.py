#parser.py
import html
import re


def clean(value: str) -> str:
    if not value:
        return ""

    value = html.unescape(value)

    # Remove Telegram markdown
    value = re.sub(r"[*_`#]", "", value)

    # Collapse whitespace
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract(pattern: str, text: str) -> str:

    match = re.search(
        pattern,
        text,
        re.IGNORECASE,
    )

    if not match:
        return ""

    return clean(match.group(1))


def parse_job(text: str):

    cleaned_text = clean(text)

    return {

        "title": extract(r"Título:\s*(.+)", cleaned_text),

        "company": extract(r"Empresa:\s*(.+)", cleaned_text),

        "location": extract(r"Local:\s*(.+)", cleaned_text),

        "contract": extract(r"Contrato:\s*(.+)", cleaned_text),

        "level": extract(r"Nível:\s*(.+)", cleaned_text),

        # Entire advertisement for scoring
        "raw_text": cleaned_text,
    }