# core/career_result.py

from dataclasses import dataclass
from typing import Any


@dataclass
class CareerJob:
    title: str
    url: str
    company: str | None = None
    location: str | None = None
    raw_data: dict[str, Any] | None = None


@dataclass
class CareerScanResult:
    success: bool
    page_good: bool
    jobs: list[CareerJob]
    message: str
