import re
import html


def clean(value: str) -> str:
    if not value:
        return ""

    value = html.unescape(value)

    # Remove Telegram markdown
    value = re.sub(r"[*_`#]", "", value)

    # Collapse multiple spaces
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return ""

    return clean(match.group(1))


def extract_link(text: str) -> str:
    match = re.search(r"https?://\S+", text)

    if not match:
        return ""

    return match.group(0)


def parse_job(text: str):

    return {
        "title": extract(r"Título:\s*(.+)", text),
        "company": extract(r"Empresa:\s*(.+)", text),
        "location": extract(r"Local:\s*(.+)", text),
        "contract": extract(r"Contrato:\s*(.+)", text),
        "level": extract(r"Nível:\s*(.+)", text),
        "link": extract_link(text),
    }