"""Career Jobs Validator for v2 (Ollama AI + Seniority + Page Details)."""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import Any
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

from v2.config import config
from v2.core.database import get_jobs_for_validation, update_job_validation
from v2.core.date_utils import is_older_than_days, normalize_published_date
from v2.core.keywords import (
    extract_technologies,
    is_qa_job_title,
    is_qa_related,
    normalize_job_title,
)
from v2.core.seniority import evaluate_seniority


GUPY_SECTION_LABELS = {
    "description": {
        "job description",
        "descrição da vaga",
        "descricao da vaga",
    },
    "responsibilities": {
        "responsibilities and assignments",
        "responsabilidades e atribuições",
        "responsabilidades e atribuicoes",
    },
    "requirements": {
        "requirements and qualifications",
        "requisitos e qualificações",
        "requisitos e qualificacoes",
    },
    "additional_information": {
        "additional information",
        "informações adicionais",
        "informacoes adicionais",
    },
    "process_stages": {
        "process stages",
        "etapas do processo",
    },
}

GUPY_NON_REMOTE_PATTERN = re.compile(
    r"\b(?:hybrid|h[ií]brido|h[ií]brida|presencial|on[- ]?site|"
    r"in[- ]office|non[- ]remote|n[aã]o remoto)\b",
    re.IGNORECASE,
)


def is_gupy_job_url(url: str) -> bool:
    """Check whether a job URL is hosted on a Gupy subdomain."""
    hostname = (urlsplit(url).hostname or "").casefold()
    return hostname == "gupy.io" or hostname.endswith(".gupy.io")


def is_gupy_remote_work_model(value: str | None) -> bool:
    """Return whether a Gupy work-model label explicitly indicates remote work."""
    normalized = normalize_job_title(value).casefold()
    if not normalized or GUPY_NON_REMOTE_PATTERN.search(normalized):
        return False
    return bool(
        re.search(
            r"\b(?:remote|remoto|remota|teletrabalho|home office|work from home)\b",
            normalized,
        )
    )


def has_gupy_non_remote_text(value: str | None) -> bool:
    """Detect explicit non-remote work-model text in a Gupy job title."""
    return bool(GUPY_NON_REMOTE_PATTERN.search(normalize_job_title(value)))


def extract_gupy_job_details(body_text: str) -> dict[str, Any]:
    """Extract structured job metadata and sections from Gupy's visible text."""
    cleaned_text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", body_text)
    cleaned_text = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned_text)
    lines = [
        normalize_job_title(line.lstrip("#").strip())
        for line in cleaned_text.splitlines()
        if normalize_job_title(line.lstrip("#").strip())
        and normalize_job_title(line.strip()) != "---"
    ]

    sections = {name: [] for name in GUPY_SECTION_LABELS}
    current_section: str | None = None
    details: dict[str, Any] = {
        "title": lines[0] if lines else "",
        "published_date": None,
        "application_deadline": None,
        "location": None,
        "contract": None,
        "work_model": None,
        "remote": None,
        "accessibility": None,
        "level": None,
    }

    section_by_heading = {
        label: section
        for section, labels in GUPY_SECTION_LABELS.items()
        for label in labels
    }
    metadata_labels = {
        "location": re.compile(r"^(?:location|local de trabalho)\s*:\s*(.*)$", re.I),
        "contract": re.compile(r"^(?:job type|tipo de vaga)\s*:\s*(.*)$", re.I),
        "work_model": re.compile(
            r"^(?:work model|modelo de trabalho)\s*:\s*(.*)$", re.I
        ),
    }
    date_labels = (
        (
            "published_date",
            re.compile(r"^(?:published on|publicada em)\s+(.+)$", re.I),
        ),
        (
            "application_deadline",
            re.compile(
                r"^(?:applications open until|inscrições abertas até|"
                r"inscricoes abertas ate)\s+(.+)$",
                re.I,
            ),
        ),
    )

    for line in lines:
        heading = line.casefold().rstrip(":")
        if heading in section_by_heading:
            current_section = section_by_heading[heading]
            continue

        if heading in ("also for pwd", "vaga também para pcd", "vaga tambem para pcd"):
            details["accessibility"] = line

        for key, pattern in date_labels:
            match = pattern.match(line)
            if match:
                details[key] = normalize_published_date(match.group(1))
                current_section = None
                break
        else:
            for key, pattern in metadata_labels.items():
                match = pattern.match(line)
                if match:
                    value = normalize_job_title(match.group(1))
                    words = value.split()
                    midpoint = len(words) // 2
                    if (
                        len(words) % 2 == 0
                        and [word.casefold() for word in words[:midpoint]]
                        == [word.casefold() for word in words[midpoint:]]
                    ):
                        value = " ".join(words[:midpoint])
                    details[key] = value or None
                    current_section = None
                    break
            else:
                if current_section:
                    sections[current_section].append(line)

    if details["work_model"]:
        details["remote"] = int(is_gupy_remote_work_model(details["work_model"]))

    title_level = re.search(
        r"\b(?:senior|s[eê]nior|sr|junior|j[uú]nior|jr|estagi[aá]ri[oa]|"
        r"est[aá]gio|trainee|pleno|mid[- ]level)\b",
        str(details["title"]),
        re.IGNORECASE,
    )
    if title_level:
        details["level"] = title_level.group(0)

    details["description"] = "\n".join(
        sections["description"] + sections["responsibilities"]
    ).strip()
    details["requirements"] = "\n".join(sections["requirements"]).strip()
    details["additional_information"] = "\n".join(
        sections["additional_information"]
    ).strip()
    details["process_stages"] = "\n".join(sections["process_stages"]).strip()
    return details


def extract_labeled_job_title(body_text: str) -> str:
    """Extract an explicitly labeled title from normalized visible page text."""
    lines = [
        normalized
        for line in body_text.splitlines()
        if (normalized := normalize_job_title(line))
    ]
    title_label = re.compile(
        r"^(?:job\s+title|position\s+title|position|cargo|t[ií]tulo|"
        r"nome\s+da\s+vaga|vaga)\s*:?\s*(.*)$",
        re.IGNORECASE,
    )
    for index, line in enumerate(lines):
        match = title_label.match(line)
        if not match:
            continue
        inline_title = normalize_job_title(match.group(1))
        if inline_title:
            return inline_title
        if index + 1 < len(lines):
            return lines[index + 1]
    return ""


async def classify_title_with_ollama(
    title: str,
    job_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call local Ollama to make the final QA and seniority decision."""
    normalized_title = normalize_job_title(title)
    if not is_qa_job_title(normalized_title):
        return {
            "is_qa_mid_level": False,
            "reason": "TITLE_NOT_QA_ROLE",
        }

    job_context = ""
    decision_scope = (
        "Only classify the job title itself. Do not infer a QA role from the company, "
        "page content, marketing text, or the word 'career'."
    )
    if job_details:
        context_keys = (
            "location",
            "contract",
            "work_model",
            "published_date",
            "application_deadline",
            "description",
            "requirements",
            "additional_information",
        )
        context = {
            key: str(job_details[key])[:3000]
            for key in context_keys
            if job_details.get(key)
        }
        job_context = f"\nExtracted Gupy job details:\n{json.dumps(context, ensure_ascii=False)}\n"
        decision_scope = (
            "Use the extracted role requirements and job details to make the final "
            "decision; do not infer a QA role from company marketing text."
        )

    prompt = f"""Decide whether this job title describes a QA/software testing position at a mid-level, pleno (not junior, internship, senior, lead, or principal). Avoid industrial and laboratory roles.
If a title explicitly lists both mid-level and senior options, such as "QA Testing Pleno/Senior", accept it as including a mid-level position.
A senior-only title is not mid-level.
{decision_scope}
Return JSON with:
{{"is_qa_mid_level": true or false, "reason": "short explanation"}}

Job title: {normalized_title}
{job_context}
"""
    try:
        import ollama

        client = ollama.AsyncClient()
        response = await client.chat(
            model=config.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0, "num_predict": 120},
        )
        content = response.message.content
        if content:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "is_qa_mid_level" in parsed:
                return {
                    "is_qa_mid_level": bool(parsed["is_qa_mid_level"]),
                    "reason": str(parsed.get("reason", "")).strip(),
                }
    except Exception as exc:
        print(f"    [!] Ollama classification unavailable ({exc}); falling back to rule-based engine.")

    # Fallback to rule engine
    is_qa = is_qa_related(title)
    is_seniority_ok, seniority_reason = evaluate_seniority(title)
    is_eligible = is_qa and is_seniority_ok
    return {
        "is_qa_mid_level": is_eligible,
        "reason": seniority_reason or ("Matched QA mid-level" if is_eligible else "Not QA mid-level"),
    }


async def run_validator(limit: int | None = None) -> None:
    """Validate discovered career jobs via AI classification and page scraping."""
    target_limit = limit or config.validation_limit
    jobs = get_jobs_for_validation(pipeline="CAREER_PAGE", limit=target_limit)

    if not jobs:
        print("\n[INFO] No pending career jobs found to validate.\n")
        return

    print("\n" + "=" * 60)
    print(f"[VALIDATE] Validating {len(jobs)} career jobs...")
    print("=" * 60)

    validated_count = 0
    discarded_count = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=config.headless)
        page = await browser.new_page()

        try:
            for index, job in enumerate(jobs, start=1):
                url = job["source_url"]
                raw_title = job.get("title") or ""
                print(f"\n[{index}/{len(jobs)}] Evaluating: {job.get('company')} - {raw_title or url}")

                ai_reason = None
                ai_status = "SKIPPED"
                gupy_job = is_gupy_job_url(url)

                # Step 1: Pre-filter title with Ollama if title is known
                if raw_title and not gupy_job:
                    ai_decision = await classify_title_with_ollama(raw_title)
                    ai_reason = ai_decision.get("reason")
                    ai_status = "PROCESSED"

                    if not ai_decision.get("is_qa_mid_level"):
                        print(f"  [DISCARD] AI rejected title: {raw_title} ({ai_reason})")
                        update_job_validation(
                            job_id=job["id"],
                            status="DISCARDED",
                            discard_reason=f"LLM_REJECTED: {ai_reason}",
                            ai_status=ai_status,
                            ai_reason=ai_reason,
                        )
                        discarded_count += 1
                        continue

                # Step 2: Open job page and extract details
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
                except Exception as exc:
                    print(f"  [!] Failed to open page: {exc}")
                    continue

                try:
                    body_text = await page.locator("body").inner_text(timeout=5000)
                except Exception:
                    body_text = ""

                gupy_details = extract_gupy_job_details(body_text) if gupy_job else {}
                work_model = gupy_details.get("work_model")
                title_text = " ".join(
                    filter(None, (gupy_details.get("title"), raw_title))
                )
                non_remote_work_model = bool(
                    (work_model and not is_gupy_remote_work_model(work_model))
                    or has_gupy_non_remote_text(title_text)
                )
                if non_remote_work_model:
                    reason = "NON_REMOTE_WORK_MODEL"
                    detected_model = (
                        work_model or raw_title or gupy_details.get("title")
                    )
                    print(
                        f"  [DISCARD] Gupy work model is not remote: {detected_model}",
                        flush=True,
                    )
                    update_job_validation(
                        job_id=job["id"],
                        status="DISCARDED",
                        title=gupy_details.get("title") or raw_title or None,
                        location=gupy_details.get("location"),
                        remote=0,
                        level=gupy_details.get("level"),
                        contract=gupy_details.get("contract"),
                        discard_reason=reason,
                        ai_status="SKIPPED",
                        ai_reason=reason,
                    )
                    discarded_count += 1
                    continue

                # Extract title if not previously known
                page_title = gupy_details.get("title", "") if gupy_job else ""
                if not page_title:
                    page_title = extract_labeled_job_title(body_text)
                if not page_title:
                    try:
                        h1 = page.locator("h1").first
                        if await h1.is_visible(timeout=1000):
                            page_title = normalize_job_title(await h1.inner_text())
                    except Exception:
                        pass

                page_title_is_qa = is_qa_job_title(page_title)
                final_title = (
                    page_title if page_title_is_qa else normalize_job_title(raw_title)
                )
                if not final_title:
                    final_title = page_title

                if not is_qa_job_title(final_title):
                    reason = "TITLE_NOT_QA_ROLE"
                    print(
                        f"  [DISCARD] Extracted title is not a QA/testing role: "
                        f"{final_title or '(no title found)'}"
                    )
                    update_job_validation(
                        job_id=job["id"],
                        status="DISCARDED",
                        title=final_title or None,
                        discard_reason=reason,
                        ai_status="PROCESSED",
                        ai_reason=reason,
                    )
                    discarded_count += 1
                    continue

                if gupy_job or final_title != normalize_job_title(raw_title):
                    ai_decision = await classify_title_with_ollama(
                        final_title,
                        job_details=gupy_details or None,
                    )
                    ai_reason = ai_decision.get("reason")
                    ai_status = "PROCESSED"
                    if not ai_decision.get("is_qa_mid_level"):
                        print(
                            f"  [DISCARD] AI rejected extracted title: "
                            f"{final_title} ({ai_reason})"
                        )
                        update_job_validation(
                            job_id=job["id"],
                            status="DISCARDED",
                            title=final_title,
                            discard_reason=f"LLM_REJECTED: {ai_reason}",
                            ai_status=ai_status,
                            ai_reason=ai_reason,
                        )
                        discarded_count += 1
                        continue

                # Technologies and date
                technologies = extract_technologies(body_text)
                pub_date = (
                    job.get("published_date")
                    or gupy_details.get("published_date")
                    or normalize_published_date(body_text)
                )
                is_stale = is_older_than_days(pub_date, days=30)
                is_seniority_ok, seniority_reason = evaluate_seniority(final_title)

                if is_stale:
                    print(f"  [DISCARD] Stale (>30 days): {final_title}")
                    update_job_validation(
                        job_id=job["id"],
                        status="DISCARDED",
                        title=final_title,
                        discard_reason="STALE_OVER_30_DAYS",
                        published_date=pub_date,
                        ai_status=ai_status,
                        ai_reason=ai_reason,
                    )
                    discarded_count += 1
                elif not is_seniority_ok:
                    print(f"  [DISCARD] {seniority_reason}: {final_title}")
                    update_job_validation(
                        job_id=job["id"],
                        status="DISCARDED",
                        title=final_title,
                        discard_reason=seniority_reason,
                        published_date=pub_date,
                        ai_status=ai_status,
                        ai_reason=ai_reason,
                    )
                    discarded_count += 1
                else:
                    print(f"  [OK] Validated: {job.get('company')} - {final_title}")
                    update_job_validation(
                        job_id=job["id"],
                        status="VALIDATED",
                        title=final_title,
                        location=gupy_details.get("location"),
                        remote=gupy_details.get("remote"),
                        level=gupy_details.get("level"),
                        contract=gupy_details.get("contract"),
                        application_url=url,
                        application_source="CAREER_PAGE",
                        description=(
                            body_text[:5000] if body_text else None
                        ),
                        technologies=technologies,
                        requirements=gupy_details.get("requirements") or None,
                        benefits=gupy_details.get("additional_information") or None,
                        published_date=pub_date,
                        ai_status=ai_status,
                        ai_reason=ai_reason,
                    )
                    validated_count += 1

                await asyncio.sleep(random.uniform(1.5, 3.0))

        finally:
            await browser.close()

    print("\n" + "=" * 60)
    print("[SUMMARY] CAREER VALIDATION METRICS")
    print("=" * 60)
    print(f" Validated (Active) : {validated_count}")
    print(f" Discarded          : {discarded_count}")
    print("=" * 60 + "\n")


def run(limit: int | None = None) -> None:
    """Synchronous entry point."""
    asyncio.run(run_validator(limit=limit))
