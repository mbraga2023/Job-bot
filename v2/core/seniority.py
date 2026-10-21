"""Canonical Seniority Evaluator for v2.

Unified business rules for filtering jobs:
- Keeps: Mid-level / Pleno positions (and combined levels that include Pleno, e.g. Pleno/Senior).
- Discards: Junior, Intern, Trainee, Senior-only, Lead, Principal, Manager.
"""

from __future__ import annotations

import re
import unicodedata

# Junior / Entry / Intern patterns
JUNIOR_PATTERNS = [
    r"\bjunior\b",
    r"\bjr\b",
    r"\bestag[ií]o\b",
    r"\bestagi[aá]ri[oa]\b",
    r"\bintern(?:ship)?\b",
    r"\btrainee\b",
    r"\bentry\s*level\b",
    r"\biniciante\b",
    r"\bassistent[e]\b",
]

# Senior / Lead / Staff patterns
SENIOR_PATTERNS = [
    r"\bs[eê]nior\b",
    r"\bsr\b",
    r"\blead\b",
    r"\btech\s*lead\b",
    r"\bprincipal\b",
    r"\bstaff\b",
    r"\bespecialista\b",
    r"\bspecialist\b",
    r"\barquiteto\b",
    r"\barchitect\b",
    r"\bhead\b",
    r"\bmanager\b",
    r"\bgerente\b",
    r"\bcoordenador[a]?\b",
    r"\bdiretor[a]?\b",
]

# Mid-level / Pleno patterns
PLENO_PATTERNS = [
    r"\bpleno\b",
    r"\bpl\b",
    r"\bmid\b",
    r"\bmiddle\b",
    r"\bmid-level\b",
    r"\bmid\s*level\b",
    r"\bintermediate\b",
]

# Combined mid-level indicators (e.g. Pleno/Senior)
COMBINED_PLENO_PATTERNS = [
    r"\bpleno\s*[/\\-]\s*s[eê]nior\b",
    r"\bmid\s*[/\\-]\s*senior\b",
    r"\bpl\s*[/\\-]\s*sr\b",
    r"\bj[uú]nior\s*[/\\-]\s*pleno\b",
    r"\bjr\s*[/\\-]\s*pl\b",
]


def normalize_text(text: str | None) -> str:
    """Normalize text by stripping accents, lowering case, and collapsing whitespace."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(without_accents.lower().split())


def is_combined_pleno(text: str) -> bool:
    """Check if text contains combined level explicitly including Pleno/Mid."""
    for pattern in COMBINED_PLENO_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def is_junior(text: str) -> bool:
    """Check if text contains junior / intern / trainee keywords."""
    for pattern in JUNIOR_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def is_senior(text: str) -> bool:
    """Check if text contains senior / lead / executive keywords."""
    for pattern in SENIOR_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def is_explicitly_pleno(text: str) -> bool:
    """Check if text explicitly states mid-level / pleno."""
    for pattern in PLENO_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def evaluate_seniority(title: str | None, level: str | None = None) -> tuple[bool, str | None]:
    """Evaluate whether a job qualifies as mid-level / pleno.

    Returns:
        (is_eligible: bool, discard_reason: str | None)
        If eligible -> (True, None)
        If discarded -> (False, reason) e.g. "SENIORITY_JUNIOR" or "SENIORITY_SENIOR"
    """
    combined = f"{normalize_text(title)} {normalize_text(level)}".strip()
    if not combined:
        return True, None

    # 1. Combined levels that include Pleno (e.g. Pleno/Senior) are ACCEPTED
    if is_combined_pleno(combined):
        return True, None

    # 2. Junior / Intern / Trainee is ALWAYS discarded
    if is_junior(combined):
        return False, "SENIORITY_JUNIOR"

    # 3. Senior / Lead / Principal without Pleno is discarded
    if is_senior(combined):
        return False, "SENIORITY_SENIOR"

    # 4. Standard Pleno or unstated level without senior/junior flags is accepted
    return True, None
