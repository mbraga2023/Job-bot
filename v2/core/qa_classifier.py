"""LLM-assisted QA job-title classification."""

from __future__ import annotations

import json

from v2.config import config
from v2.core.keywords import is_qa_job_title, normalize_job_title


async def _classify_with_ollama(title: str) -> bool:
    import ollama

    client = ollama.AsyncClient()
    response = await client.chat(
        model=config.ollama_model,
        messages=[
            {
                "role": "user",
                "content": f"""Decide whether this job title describes a software quality assurance
or software testing role. Reject industrial/product quality control, inspection,
research, business analysis, monitoring, and other non-software-quality roles.
Classify only the title. Return JSON: {{"is_qa": true or false}}

Job title: {title}""",
            }
        ],
        format="json",
        options={"temperature": 0, "num_predict": 80},
    )
    content = response.message.content
    if not content:
        raise ValueError("Ollama returned an empty QA classification.")

    result = json.loads(content)
    if not isinstance(result, dict) or not isinstance(result.get("is_qa"), bool):
        raise ValueError("Ollama returned an invalid QA classification.")
    return result["is_qa"]


async def is_qa_title(title: str | None) -> bool:
    """Classify a job title with Ollama, falling back to the deterministic filter."""
    normalized_title = normalize_job_title(title)
    if not is_qa_job_title(normalized_title):
        return False

    try:
        return await _classify_with_ollama(normalized_title)
    except Exception as exc:
        print(f"    [!] Ollama QA classification unavailable ({exc}); using title rules.")
        return is_qa_job_title(normalized_title)
