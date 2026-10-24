"""Consolidated QA Keywords, Search Terms, and Tool Definitions for v2."""

from __future__ import annotations

import html
import json
import re
import unicodedata

# Search terms used when querying career portals and search inputs
QA_SEARCH_TERMS: list[str] = [
    # English
    "QA",
    "Quality Assurance",
    "Quality Engineer",
    "Software Tester",
    "Test Engineer",
    "Test Analyst",
    "Test Automation",
    "QA Automation",
    "SDET",
    "Software Quality",
    "Quality Engineering",
    "Testing Engineer",
    "Quality Analyst",
    "Automation Engineer",
    "Automated Testing",
    "Software Testing",
    "QA Engineer",
    "QA Analyst",
    "Tester",
    "QE",
    # Portuguese
    "Analista de QA",
    "Analista de Testes",
    "Analista de Qualidade",
    "Engenheiro de Testes",
    "Engenheira de Testes",
    "Automação de Testes",
    "Especialista em Automação de Testes",
    "Qualidade de Software",
    "Testes de Software",
]

# Require role-specific evidence in the title before asking the LLM to classify it.
QA_TITLE_PATTERN = re.compile(
    r"\b(?:"
    r"qa|sdet|qe|"
    r"quality\s+assurance|"
    r"quality\s+(?:engineer(?:ing)?|analyst)|"
    r"software\s+(?:tester|testing|quality)|"
    r"test(?:ing)?\s+(?:engineer|analyst|automation)|"
    r"qa\s+(?:automation|analyst|engineer)|"
    r"automation\s+engineer|"
    r"tester|"
    r"analista\s+de\s+(?:qa|testes?|teste\s+de\s+(?:software|sistemas)|automacao\s+de\s+testes|qualidade)|"
    r"engenheir[oa]\s+de\s+testes|"
    r"automacao\s+de\s+testes|"
    r"qualidade\s+de\s+software|"
    r"testes\s+de\s+software"
    r")\b",
    re.IGNORECASE,
)

QA_EVIDENCE_TECH_PATTERNS = (
    r"\bselenium\b",
    r"\bplaywright\b",
    r"\bcypress\b",
    r"\bistqb\b",
    r"\bappium\b",
    r"\brobot\s*framework\b",
    r"\bpostman\b",
    r"\brest[- ]?assured\b",
    r"\bjmeter\b",
    r"\bk6\b",
    r"\bjest\b",
    r"\bpytest\b",
    r"\bjunit\b",
    r"\btestng\b",
    r"\bcucumber\b",
    r"\bwebdriverio\b",
    r"\bkarate\b",
)

NON_QA_TITLE_PREFIXES: tuple[str, ...] = (
    "Monitor de Qualidade",
    "Gerente Executivo de Qualidade",
    "Consultor de Validação",
    "Especialista em Desenvolvimento do Produto",
    "Pesquisador",
    "Inspetor de qualidade",
    "Analista de sistemas de gestão",
    "Analista de Controle de Qualidade Pleno",
    "Analista de negócios",
    "Analista de Monitoramento",
    "Gestão de qualidade",
    "Assistente de qualidade",
)

NON_JOB_TITLE_PATTERN = re.compile(
    r"\b(?:"
    r"view\s+all\s+jobs|see\s+all\s+jobs|"
    r"ver\s+todas\s+as\s+vagas|carregar\s+mais|load\s+more|"
    r"apply\s+now|learn\s+more|"
    r"turn\s+your\b.*\bcareer|"
    r"career\s+opportunit(?:y|ies)|"
    r"join\s+our\s+talent\s+community"
    r")\b",
    re.IGNORECASE,
)

_NON_QA_TITLE_KEYS = tuple(
    re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKD", title)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold(),
    ).strip()
    for title in NON_QA_TITLE_PREFIXES
)

# Classification keywords matching QA roles
QA_KEYWORDS: tuple[str, ...] = (
    "qa",
    "quality assurance",
    "quality engineer",
    "quality analyst",
    "software quality",
    "qualidade de software",
    "analista de qualidade",
    "analista de testes",
    "engenheiro de testes",
    "engenheira de testes",
    "automação de testes",
    "test automation",
    "automated testing",
    "tester",
    "testing",
    "teste",
    "testes",
    "test engineer",
    "test analyst",
    "sdet",
)

# Testing tools and technologies to tag
QA_TECH_CATALOG: dict[str, list[str]] = {
    "Playwright": [r"\bplaywright\b"],
    "Cypress": [r"\bcypress\b"],
    "Selenium": [r"\bselenium\b"],
    "ISTQB": [r"\bistqb\b"],
    "Robot Framework": [r"\brobot\s*framework\b"],
    "Appium": [r"\bappium\b"],
    "Postman": [r"\bpostman\b"],
    "RestAssured": [r"\brest\s*assured\b", r"\brest-assured\b"],
    "JMeter": [r"\bjmeter\b"],
    "k6": [r"\bk6\b"],
    "Jest": [r"\bjest\b"],
    "Pytest": [r"\bpytest\b"],
    "JUnit": [r"\bjunit\b"],
    "TestNG": [r"\btestng\b"],
    "WebdriverIO": [r"\bwebdriverio\b"],
    "Karate": [r"\bkarate\b"],
    "Cucumber / BDD": [r"\bcucumber\b", r"\bbdd\b", r"\bgji?erkin\b"],
    "CI/CD": [
        r"\bci[/\\-]?cd\b",
        r"\bjenkins\b",
        r"\bgithub\s*actions\b",
        r"\bgitlab\b",
    ],
    "Docker": [r"\bdocker\b"],
    "SQL": [r"\bsql\b", r"\bpostgres\b", r"\bmysql\b"],
    "Python": [r"\bpython\b"],
    "JavaScript / TypeScript": [
        r"\bjavascript\b",
        r"\btypescript\b",
        r"\bjs\b",
        r"\bts\b",
    ],
    "Java": [r"\bjava\b"],
}


def normalize_job_title(title: str | None) -> str:
    """Normalize visible title text like the V1 career analyzer."""
    if not title:
        return ""
    unescaped = html.unescape(str(title))
    normalized = unicodedata.normalize("NFKC", unescaped)
    return " ".join(normalized.split()).strip(" \t\r\n-–—|:")


def is_qa_job_title(title: str | None) -> bool:
    """Check a normalized job title for role-specific QA/software-testing evidence."""
    normalized = normalize_job_title(title)
    if not normalized or len(normalized) > 180:
        return False
    if is_non_qa_job_title(normalized):
        return False
    if NON_JOB_TITLE_PATTERN.search(normalized):
        return False
    title_key = unicodedata.normalize("NFKD", normalized)
    title_key = "".join(ch for ch in title_key if not unicodedata.combining(ch))
    return bool(QA_TITLE_PATTERN.search(title_key))


def has_qa_technology(technologies: list[str] | str | None) -> bool:
    """Check whether extracted technologies include known QA/testing tools."""
    if not technologies:
        return False
    if isinstance(technologies, str):
        try:
            parsed = json.loads(technologies)
        except json.JSONDecodeError:
            values = [technologies]
        else:
            values = parsed if isinstance(parsed, list) else [technologies]
    else:
        values = technologies

    text = " ".join(str(value) for value in values)
    return any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in QA_EVIDENCE_TECH_PATTERNS
    )


def is_non_qa_job_title(title: str | None) -> bool:
    """Check whether a normalized title starts with an explicitly excluded role."""
    normalized = normalize_job_title(title)
    normalized_key = re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKD", normalized)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold(),
    ).strip()
    return any(
        normalized_key == prefix or normalized_key.startswith(f"{prefix} ")
        for prefix in _NON_QA_TITLE_KEYS
    )


def is_qa_related(text: str | None) -> bool:
    """Check if the given text matches QA role keywords."""
    if not text:
        return False
    if is_non_qa_job_title(text):
        return False
    lower = text.lower()
    for kw in QA_KEYWORDS:
        # Match as word boundary if short (<= 4 chars like 'qa', 'sdet')
        if len(kw) <= 4:
            if re.search(rf"\b{re.escape(kw)}\b", lower):
                return True
        elif kw in lower:
            return True
    return False


def extract_technologies(text: str | None) -> list[str]:
    """Extract known QA technologies mentioned in text."""
    if not text:
        return []
    found: list[str] = []
    lower = text.lower()
    for tech_name, patterns in QA_TECH_CATALOG.items():
        if any(re.search(pat, lower) for pat in patterns):
            found.append(tech_name)
    return found
