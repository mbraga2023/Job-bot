"""Unit tests for deterministic career title validation."""

from __future__ import annotations

import asyncio
import json
import unittest
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


class TestCareerValidatorTitleChecks(unittest.TestCase):
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
        page = MagicMock()
        page.goto = AsyncMock()
        page.locator.return_value = body
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
