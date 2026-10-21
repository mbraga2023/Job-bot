"""Career Sources Importer for v2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from v2.core.database import insert_career_source


def import_sources_from_json(json_path: str | Path) -> dict[str, int]:
    """Import company career sources from a JSON file into career_sources table."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Career sources JSON file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON file must contain an array of company source objects.")

    inserted = 0
    skipped = 0

    for item in data:
        company = (item.get("company") or "").strip()
        careers_url = (item.get("careers_url") or "").strip()
        search_url = (item.get("search_url") or "").strip() or None
        source_type = (item.get("source_type") or "CAREER_PAGE").strip()

        if not company or not careers_url:
            skipped += 1
            continue

        row_id = insert_career_source(
            company=company,
            careers_url=careers_url,
            search_url=search_url,
            source_type=source_type,
        )

        if row_id:
            inserted += 1
            print(f" [+] Imported source: {company} ({careers_url})")
        else:
            skipped += 1

    print(f"\n[OK] Import complete: {inserted} added, {skipped} skipped.")
    return {"inserted": inserted, "skipped": skipped}


def import_sources_from_payload(sources: list[dict[str, Any]]) -> dict[str, int]:
    """Import sources from a list of dicts (e.g. from Dashboard form/upload)."""
    inserted = 0
    skipped = 0

    for item in sources:
        company = (item.get("company") or "").strip()
        careers_url = (item.get("careers_url") or "").strip()
        search_url = (item.get("search_url") or "").strip() or None
        source_type = (item.get("source_type") or "CAREER_PAGE").strip()

        if not company or not careers_url:
            skipped += 1
            continue

        row_id = insert_career_source(
            company=company,
            careers_url=careers_url,
            search_url=search_url,
            source_type=source_type,
        )

        if row_id:
            inserted += 1
        else:
            skipped += 1

    return {"inserted": inserted, "skipped": skipped}
