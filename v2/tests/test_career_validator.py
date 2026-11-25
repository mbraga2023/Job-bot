"""Unit tests for deterministic career title validation."""

from __future__ import annotations

import asyncio
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from v2.flows.careers.validator import (
    classify_title_with_ollama,
    extract_gupy_job_details,
    extract_labeled_job_title,
    has_gupy_non_remote_text,
    is_gupy_remote_work_model,
    run_validator,
)
from v2.flows.careers import validator


class TestCareerValidatorTitleChecks(unittest.TestCase):
    def run_validation(
        self,
        job: dict,
        page_text: str = "",
        *,
        h1_text: str | None = None,
        goto_error: Exception | None = None,
        body_error: Exception | None = None,
        decision: dict | None = None,
    ):
        body = MagicMock()
        body.inner_text = AsyncMock(side_effect=body_error, return_value=page_text)
        heading = MagicMock()
        heading.first = heading
        heading.is_visible = AsyncMock(return_value=h1_text is not None)
        heading.inner_text = AsyncMock(return_value=h1_text or "")
        page = MagicMock()
        page.goto = AsyncMock(side_effect=goto_error)
        page.locator.side_effect = lambda selector: body if selector == "body" else heading
        browser = SimpleNamespace(
            new_page=AsyncMock(return_value=page),
            close=AsyncMock(),
        )
        playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch=AsyncMock(return_value=browser))
        )
        playwright_context = AsyncMock()
        playwright_context.__aenter__.return_value = playwright

        with (
            patch.object(validator, "get_jobs_for_validation", return_value=[job]),
            patch.object(validator, "async_playwright", return_value=playwright_context),
            patch.object(
                validator,
                "classify_title_with_ollama",
                new_callable=AsyncMock,
                return_value=decision or {
                    "is_qa_mid_level": True,
                    "reason": "Accepted",
                },
            ) as classify,
            patch.object(validator, "update_job_validation") as update,
            patch.object(validator.asyncio, "sleep", new_callable=AsyncMock) as sleep,
            patch.object(validator.random, "uniform", return_value=1.5),
            redirect_stdout(StringIO()),
        ):
            asyncio.run(run_validator(limit=1))

        return page, browser, classify, update, sleep

    def test_empty_queue_does_not_start_playwright(self) -> None:
        with (
            patch.object(validator, "get_jobs_for_validation", return_value=[]),
            patch.object(validator, "async_playwright") as start_browser,
            redirect_stdout(StringIO()),
        ):
            asyncio.run(run_validator(limit=1))

        start_browser.assert_not_called()

    def test_known_title_rejected_by_ai_before_navigation(self) -> None:
        page, browser, classify, update, _sleep = self.run_validation(
            {
                "id": 51,
                "company": "Example",
                "source_url": "https://example.com/careers/51",
                "title": "QA Engineer Pleno",
            },
            decision={"is_qa_mid_level": False, "reason": "Not eligible"},
        )

        classify.assert_awaited_once_with("QA Engineer Pleno")
        page.goto.assert_not_awaited()
        browser.close.assert_awaited_once()
        update.assert_called_once_with(
            job_id=51,
            status="DISCARDED",
            discard_reason="LLM_REJECTED: Not eligible",
            ai_status="PROCESSED",
            ai_reason="Not eligible",
        )

    def test_navigation_failure_leaves_job_pending_and_closes_browser(self) -> None:
        page, browser, _classify, update, _sleep = self.run_validation(
            {
                "id": 52,
                "source_url": "https://example.com/careers/52",
                "title": "",
            },
            goto_error=RuntimeError("navigation failed"),
        )

        page.goto.assert_awaited_once()
        browser.close.assert_awaited_once()
        update.assert_not_called()

    def test_h1_title_is_classified_and_validated_with_extracted_details(self) -> None:
        page_text = "About the role\nBuild tests with Playwright"
        page, _browser, classify, update, sleep = self.run_validation(
            {
                "id": 53,
                "company": "Example",
                "source_url": "https://example.com/careers/53",
                "title": "",
            },
            page_text,
            h1_text="QA Engineer Pleno",
        )

        classify.assert_awaited_once_with("QA Engineer Pleno", job_details=None)
        page.locator.assert_any_call("h1")
        update.assert_called_once_with(
            job_id=53,
            status="VALIDATED",
            title="QA Engineer Pleno",
            location=None,
            remote=None,
            level=None,
            contract=None,
            application_url="https://example.com/careers/53",
            application_source="CAREER_PAGE",
            description=page_text,
            technologies=["Playwright"],
            requirements=None,
            benefits=None,
            published_date=None,
            ai_status="PROCESSED",
            ai_reason="Accepted",
        )
        sleep.assert_awaited_once_with(1.5)

    def test_gupy_title_uses_content_wrapper_heading_instead_of_skip_link(self) -> None:
        page, _browser, classify, update, _sleep = self.run_validation(
            {
                "id": 58,
                "company": "Instituto Eldorado",
                "source_url": (
                    "https://institutoeldorado.gupy.io/jobs/12594277"
                    "?jobBoardSource=gupy_public_page"
                ),
                "title": "Pular para o conteúdo principal",
            },
            "## Pular para o conteúdo principal\n"
            "## QA Engineer Pleno\n"
            "## Responsabilidades e atribuições\nExecutar testes.",
            h1_text="QA Engineer Pleno",
        )

        page.locator.assert_any_call(
            "xpath=//*[@id='main']//*[@data-testid='content-wrapper']//*[@id='h1']"
        )
        classify.assert_awaited_once()
        self.assertEqual(classify.await_args.args[0], "QA Engineer Pleno")
        update.assert_called_once()
        self.assertEqual(update.call_args.kwargs["status"], "VALIDATED")
        self.assertEqual(update.call_args.kwargs["title"], "QA Engineer Pleno")

    def test_non_qa_extracted_title_is_discarded_without_classification(self) -> None:
        _page, _browser, classify, update, _sleep = self.run_validation(
            {
                "id": 54,
                "source_url": "https://example.com/careers/54",
                "title": "",
            },
            "Position: Molder - Weekend Night Shift",
        )

        classify.assert_not_awaited()
        update.assert_called_once_with(
            job_id=54,
            status="DISCARDED",
            title="Molder - Weekend Night Shift",
            discard_reason="TITLE_NOT_QA_ROLE",
            ai_status="PROCESSED",
            ai_reason="TITLE_NOT_QA_ROLE",
        )

    def test_stale_and_senior_jobs_are_discarded_after_classification(self) -> None:
        cases = (
            (
                {
                    "id": 55,
                    "source_url": "https://example.com/careers/55",
                    "title": "QA Engineer Pleno",
                    "published_date": "2020-01-01",
                },
                "Job Title: QA Engineer Pleno",
                "STALE_OVER_30_DAYS",
            ),
            (
                {
                    "id": 56,
                    "source_url": "https://example.com/careers/56",
                    "title": "QA Engineer Senior",
                },
                "Job Title: QA Engineer Senior",
                "SENIORITY_SENIOR",
            ),
        )
        for job, page_text, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                _page, _browser, classify, update, sleep = self.run_validation(
                    job,
                    page_text,
                )

                classify.assert_awaited_once_with(job["title"])
                self.assertEqual(update.call_args.kwargs["status"], "DISCARDED")
                self.assertEqual(
                    update.call_args.kwargs["discard_reason"],
                    expected_reason,
                )
                sleep.assert_awaited_once()

    def test_gupy_final_title_rejection_includes_extracted_context(self) -> None:
        page_text = """# QA Engineer Pleno
Modelo de trabalho: Remoto
Requisitos e qualificações
Experiência com testes
"""
        _page, _browser, classify, update, _sleep = self.run_validation(
            {
                "id": 57,
                "source_url": "https://example.gupy.io/jobs/57",
                "title": "",
            },
            page_text,
            decision={"is_qa_mid_level": False, "reason": "Intern role"},
        )

        classify.assert_awaited_once()
        title, = classify.await_args.args
        self.assertEqual(title, "QA Engineer Pleno")
        self.assertEqual(classify.await_args.kwargs["job_details"]["work_model"], "Remoto")
        self.assertEqual(update.call_args.kwargs["discard_reason"], "LLM_REJECTED: Intern role")

    def test_ollama_invalid_json_uses_rule_based_classification(self) -> None:
        client = SimpleNamespace(
            chat=AsyncMock(
                return_value=SimpleNamespace(
                    message=SimpleNamespace(content="not json")
                )
            )
        )
        with patch("ollama.AsyncClient", return_value=client), redirect_stdout(StringIO()):
            decision = asyncio.run(
                classify_title_with_ollama("QA Engineer Pleno")
            )

        self.assertTrue(decision["is_qa_mid_level"])
        self.assertEqual(decision["reason"], "Matched QA mid-level")

    def test_extracts_and_normalizes_labeled_title(self) -> None:
        title = extract_labeled_job_title(
            "Company: Example\nJob Title:\n  QA Engineer - Pleno  \nLocation: Remote"
        )
        self.assertEqual(title, "QA Engineer - Pleno")

    def test_rejects_unrelated_titles_without_calling_ollama(self) -> None:
        for title in (
            "Molder - Weekend Night Shift",
            "Turn your gaming skills into a career at Volvo Group",
        ):
            decision = asyncio.run(classify_title_with_ollama(title))
            self.assertFalse(decision["is_qa_mid_level"])
            self.assertEqual(decision["reason"], "TITLE_NOT_QA_ROLE")

    def test_extracts_gupy_metadata_and_portuguese_sections(self) -> None:
        details = extract_gupy_job_details(
            """# Estagiário (a) - Quality Assurance (QA)

Publicada em 14 de outubro de 2026
Inscrições abertas até 26 de outubro de 2026

Local de trabalho: Manaus - AM ![location icon](https://example.com/place.svg) Manaus - AM
Tipo de vaga: Estágio
Modelo de trabalho: Presencial
Vaga também para PcD

## Descrição da vaga
Somos positivos e tecnológicos.

## Responsabilidades e atribuições
- Executar Testes de Software.

## Requisitos e qualificações
Conhecimento em Testes de Software.

## Informações adicionais
Vale transporte.

## Etapas do processo
1. Cadastro
"""
        )

        self.assertEqual(details["title"], "Estagiário (a) - Quality Assurance (QA)")
        self.assertEqual(details["published_date"], "2026-10-14")
        self.assertEqual(details["application_deadline"], "2026-10-26")
        self.assertEqual(details["location"], "Manaus - AM")
        self.assertEqual(details["contract"], "Estágio")
        self.assertEqual(details["work_model"], "Presencial")
        self.assertEqual(details["remote"], 0)
        self.assertEqual(details["level"], "Estagiário")
        self.assertIn("Executar Testes de Software", details["description"])
        self.assertEqual(details["requirements"], "Conhecimento em Testes de Software.")
        self.assertEqual(details["additional_information"], "Vale transporte.")
        self.assertEqual(details["process_stages"], "1. Cadastro")

    def test_gupy_work_model_only_passes_explicit_remote_values(self) -> None:
        for value in ("Remote", "Remoto", "Remota", "Home office"):
            with self.subTest(value=value):
                self.assertTrue(is_gupy_remote_work_model(value))

        for value in ("Híbrido", "Presencial", "Hybrid / Remote", "Não remoto"):
            with self.subTest(value=value):
                self.assertFalse(is_gupy_remote_work_model(value))

    def test_gupy_title_detects_hybrid_and_other_non_remote_markers(self) -> None:
        for title in (
            "Analista de Qualidade de Software Indaiatuba - SP e Híbrido Efetivo",
            "QA Analyst Hybrid",
            "QA Engineer Presencial",
        ):
            with self.subTest(title=title):
                self.assertTrue(has_gupy_non_remote_text(title))

        self.assertFalse(
            has_gupy_non_remote_text("Senior QA Automation Engineer - Remoto")
        )

    def test_gupy_hybrid_job_is_discarded_before_llm(self) -> None:
        page_text = """# Senior QA Automation Engineer
Local de trabalho: Indaiatuba - SP
Tipo de vaga: Efetivo
Vaga também para PcD
"""
        body = MagicMock()
        body.inner_text = AsyncMock(return_value=page_text)
        heading = MagicMock()
        heading.first = heading
        heading.is_visible = AsyncMock(return_value=False)
        page = MagicMock()
        page.goto = AsyncMock()
        page.locator.side_effect = lambda selector: (
            body if selector == "body" else heading
        )
        browser = SimpleNamespace(
            new_page=AsyncMock(return_value=page),
            close=AsyncMock(),
        )
        playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch=AsyncMock(return_value=browser))
        )
        playwright_context = AsyncMock()
        playwright_context.__aenter__.return_value = playwright
        job = {
            "id": 42,
            "company": "Example",
            "source_url": "https://verity.gupy.io/job/123",
            "title": (
                "Senior QA Automation Engineer Indaiatuba - SP e Híbrido Efetivo"
            ),
        }

        with (
            patch(
                "v2.flows.careers.validator.get_jobs_for_validation",
                return_value=[job],
            ),
            patch(
                "v2.flows.careers.validator.async_playwright",
                return_value=playwright_context,
            ),
            patch(
                "v2.flows.careers.validator.classify_title_with_ollama",
                new_callable=AsyncMock,
            ) as classify,
            patch("v2.flows.careers.validator.update_job_validation") as update,
        ):
            asyncio.run(run_validator(limit=1))

        classify.assert_not_awaited()
        update.assert_called_once_with(
            job_id=42,
            status="DISCARDED",
            title="Senior QA Automation Engineer",
            location="Indaiatuba - SP",
            remote=0,
            level="Senior",
            contract="Efetivo",
            discard_reason="NON_REMOTE_WORK_MODEL",
            ai_status="SKIPPED",
            ai_reason="NON_REMOTE_WORK_MODEL",
        )

    def test_llm_receives_structured_gupy_details_for_final_decision(self) -> None:
        response = SimpleNamespace(
            message=SimpleNamespace(
                content=json.dumps({"is_qa_mid_level": False, "reason": "Internship"})
            )
        )
        client = SimpleNamespace(chat=AsyncMock(return_value=response))
        details = {
            "location": "Manaus - AM",
            "contract": "Estágio",
            "work_model": "Presencial",
            "requirements": "Testes de Software",
        }

        with patch("ollama.AsyncClient", return_value=client):
            decision = asyncio.run(
                classify_title_with_ollama(
                    "Estagiário QA Engineer",
                    job_details=details,
                )
            )

        self.assertFalse(decision["is_qa_mid_level"])
        prompt = client.chat.await_args.kwargs["messages"][0]["content"]
        self.assertIn('"contract": "Estágio"', prompt)
        self.assertIn('"requirements": "Testes de Software"', prompt)


if __name__ == "__main__":
    unittest.main()
