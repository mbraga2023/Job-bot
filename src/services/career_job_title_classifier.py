"""LLM-based title validation for career jobs."""

import json
from typing import TypedDict

import ollama

LLAMA_MODEL = "llama3.2:1b"


class TitleDecision(TypedDict):
    is_qa_mid_level: bool
    reason: str


async def classify_career_job_title(title: str) -> TitleDecision:
    prompt = f"""
Decide whether this job title describes a QA/software testing position
at a mid-level (not junior, internship, senior, lead, or principal).
Only use evidence in the title. Return JSON with:
{{"is_qa_mid_level": true or false, "reason": "short explanation"}}

Job title: {title}
"""
    response = await ollama.AsyncClient().chat(
        model=LLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        think=False,
        format="json",
        options={"temperature": 0, "num_predict": 120},
    )

    content = response.message.content
    if not content:
        raise ValueError("Llama returned an empty title-classification response.")

    try:
        decision = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Llama returned invalid JSON for title classification.") from exc

    if not isinstance(decision, dict) or not isinstance(
        decision.get("is_qa_mid_level"), bool
    ):
        raise ValueError(
            "Llama response must contain a boolean 'is_qa_mid_level' field."
        )

    reason = decision.get("reason", "")
    if not isinstance(reason, str):
        raise ValueError("Llama response 'reason' must be a string.")
    reason = reason.strip() or "Llama classified the title as not mid-level QA."

    return {"is_qa_mid_level": decision["is_qa_mid_level"], "reason": reason}
