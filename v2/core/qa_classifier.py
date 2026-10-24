"""LLM-assisted QA job-title classification."""

from __future__ import annotations

import json

from v2.config import config
from v2.core.keywords import (
    NON_QA_TITLE_PREFIXES,
)


async def review_job_with_ollama(
    title: str,
    level: str | None,
    description: str | None,
    remote: bool,
    technologies: list[str] | str | None,
) -> dict[str, str | bool]:
    """Make the final QA-job eligibility decision after deterministic validation."""
    import ollama

    excluded_titles = "\n".join(f"- {excluded}" for excluded in NON_QA_TITLE_PREFIXES)
    description_text = (description or "").strip()[:4000]
    if isinstance(technologies, str):
        try:
            parsed_technologies = json.loads(technologies)
        except json.JSONDecodeError:
            parsed_technologies = [technologies]
    else:
        parsed_technologies = technologies or []
    if not isinstance(parsed_technologies, list):
        parsed_technologies = [str(parsed_technologies)]
    technologies_text = ", ".join(str(item) for item in parsed_technologies) or "Not provided"
    client = ollama.AsyncClient()
    response = await client.chat(
        model=config.ollama_model,
        messages=[
            {
                "role": "user",
                "content": f"""Make the final eligibility decision for this job, after deterministic
checks have confirmed a QA-related title, remote work, and acceptable seniority.
Verify from the job details that this is genuinely a software QA/software testing role,
is remote, and is not a junior, internship, trainee, senior-only, lead, or principal role.
Cross-check the job title against the technologies list. Selenium, Playwright, Cypress,
ISTQB, Appium, Robot Framework, Postman, REST Assured, JMeter, k6, Jest, Pytest, JUnit,
TestNG, Cucumber, WebdriverIO, or Karate are strong evidence of QA/testing work and
should make an ambiguous title count as QA. Generic programming tools alone are not
enough to establish a QA role.
Reject industrial/product quality control, inspection, research, business analysis,
monitoring, and other non-software-quality roles.
These known non-QA titles must be rejected even if they mention quality:
{excluded_titles}
Return JSON: {{"eligible": true or false, "reason": "one short sentence, at most 15 words"}}

Job title: {title}
Seniority: {level or "Not specified"}
Remote confirmed: {remote}
Technologies: {technologies_text}
Job description:
{description_text or "Not provided"}""",
            }
        ],
        format={
            "type": "object",
            "properties": {
                "eligible": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["eligible", "reason"],
            "additionalProperties": False,
        },
        options={"temperature": 0, "num_predict": 256},
    )
    content = response.message.content
    if not content:
        raise ValueError("Ollama returned an empty final job review.")

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ollama returned malformed JSON for final job review: {exc}") from exc

    if (
        not isinstance(result, dict)
        or not isinstance(result.get("eligible"), bool)
        or not isinstance(result.get("reason"), str)
    ):
        raise ValueError("Ollama returned an invalid final job review.")
    return {"eligible": result["eligible"], "reason": result["reason"].strip()}
