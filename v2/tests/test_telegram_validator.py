"""Tests for deterministic Telegram gates and final Ollama review."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from v2.config import config
from v2.flows.telegram.analyzers.meupadrinho import MeuPadrinhoAnalyzer
from v2.flows.telegram import validator


class FakePage:
    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        pass


class FakePlaywrightContext:
    def __init__(self) -> None:
        self.page = FakePage()
        self.browser_context = SimpleNamespace(
            pages=[self.page],
            close=AsyncMock(),
        )
        self.chromium = SimpleNamespace(
            launch_persistent_context=AsyncMock(return_value=self.browser_context)
        )

    async def __aenter__(self):
        return SimpleNamespace(chromium=self.chromium)

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass


class TestTelegramValidatorClassification(unittest.TestCase):
    def run_validation(self, job: dict, extracted: dict, final_review=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(validator, "get_jobs_for_validation", return_value=[job]),
                patch.object(validator, "async_playwright", return_value=FakePlaywrightContext()),
                patch.object(validator, "MeuPadrinhoAnalyzer") as analyzer_class,
                patch.object(
                    validator,
                    "review_job_with_ollama",
                    new_callable=AsyncMock,
                    return_value=final_review or {"eligible": True, "reason": "Approved"},
                ) as review,
                patch.object(validator, "update_job_validation") as update,
                patch.object(config, "meupadrinho_profile_dir", Path(temp_dir)),
                patch.object(config, "headless", True),
                patch.object(config, "timeout_ms", 1000),
                patch.object(config, "validate_delay_min", 0),
                patch.object(config, "validate_delay_max", 0),
                patch.object(validator.random, "uniform", return_value=0),
            ):
                analyzer_class.return_value.analyze = AsyncMock(return_value=extracted)
                asyncio.run(validator.run_validator(limit=1))

        return review, update

    def test_non_qa_title_is_rejected_without_llm(self) -> None:
        review, update = self.run_validation(
            {
                "id": 22,
                "source_url": "https://example.com/job/22",
                "title": "Analista de negócios",
                "remote": 1,
            },
            {
                "title": "Analista de negócios",
                "remote": True,
                "job_status": "OPEN",
            },
        )

        review.assert_not_awaited()
        self.assertEqual(update.call_args.kwargs["discard_reason"], "NON_QA_TITLE")
        self.assertEqual(update.call_args.kwargs["category"], "OTHER")
        self.assertEqual(update.call_args.kwargs["ai_status"], "PROCESSED")

    def test_non_remote_job_is_rejected_without_llm(self) -> None:
        review, update = self.run_validation(
            {
                "id": 23,
                "source_url": "https://example.com/job/23",
                "title": "QA Engineer Pleno",
                "remote": 1,
            },
            {
                "title": "QA Engineer Pleno",
                "remote": False,
                "job_status": "OPEN",
            },
        )

        review.assert_not_awaited()
        self.assertEqual(update.call_args.kwargs["discard_reason"], "NOT_REMOTE")
        self.assertEqual(update.call_args.kwargs["remote"], 0)
        self.assertEqual(update.call_args.kwargs["ai_status"], "PROCESSED")

    def test_seniority_is_rejected_without_llm(self) -> None:
        review, update = self.run_validation(
            {
                "id": 24,
                "source_url": "https://example.com/job/24",
                "title": "QA Engineer Senior",
                "remote": 1,
            },
            {
                "title": "QA Engineer Senior",
                "remote": True,
                "level": "Senior",
                "job_status": "OPEN",
            },
        )

        review.assert_not_awaited()
        self.assertEqual(update.call_args.kwargs["discard_reason"], "SENIORITY_SENIOR")
        self.assertEqual(update.call_args.kwargs["ai_status"], "PROCESSED")

    def test_llm_final_review_runs_only_after_all_three_gates(self) -> None:
        review, update = self.run_validation(
            {
                "id": 25,
                "source_url": "https://example.com/job/25",
                "title": "QA Engineer Pleno",
                "remote": 1,
            },
            {
                "title": "QA Engineer Pleno",
                "remote": True,
                "level": "Pleno",
                "description": "Test software applications.",
                "technologies": ["Selenium", "ISTQB"],
                "job_status": "OPEN",
            },
        )

        review.assert_awaited_once_with(
            title="QA Engineer Pleno",
            level="Pleno",
            description="Test software applications.",
            remote=True,
            technologies=["Selenium", "ISTQB"],
        )
        self.assertEqual(update.call_args.kwargs["status"], "VALIDATED")
        self.assertEqual(update.call_args.kwargs["ai_status"], "PROCESSED")

    def test_reported_titles_keep_seniority_discard_reasons(self) -> None:
        test_cases = (
            ("Analista de Teste de Software Jr.", "SENIORITY_JUNIOR"),
            (
                "Analista de Automação de Testes Sênior - Perfil II",
                "SENIORITY_SENIOR",
            ),
        )
        for index, (title, expected_reason) in enumerate(test_cases, start=30):
            with self.subTest(title=title):
                review, update = self.run_validation(
                    {
                        "id": index,
                        "source_url": f"https://example.com/job/{index}",
                        "title": title,
                        "remote": 1,
                    },
                    {
                        "title": title,
                        "remote": True,
                        "job_status": "OPEN",
                    },
                )

                review.assert_not_awaited()
                self.assertEqual(
                    update.call_args.kwargs["discard_reason"],
                    expected_reason,
                )
                self.assertEqual(update.call_args.kwargs["category"], "QA")

    def test_technology_evidence_is_cross_checked_by_final_llm(self) -> None:
        review, _ = self.run_validation(
            {
                "id": 32,
                "source_url": "https://example.com/job/32",
                "title": "Analista de Teste de Sistemas",
                "remote": 1,
            },
            {
                "title": "Analista de Teste de Sistemas",
                "remote": True,
                "level": "Pleno",
                "technologies": ["Playwright", "Cypress", "ISTQB"],
                "job_status": "OPEN",
            },
        )

        review.assert_awaited_once_with(
            title="Analista de Teste de Sistemas",
            level="Pleno",
            description=None,
            remote=True,
            technologies=["Playwright", "Cypress", "ISTQB"],
        )

    def test_llm_final_rejection_discards_job(self) -> None:
        review, update = self.run_validation(
            {
                "id": 26,
                "source_url": "https://example.com/job/26",
                "title": "QA Engineer Pleno",
                "remote": 1,
            },
            {
                "title": "QA Engineer Pleno",
                "remote": True,
                "level": "Pleno",
                "job_status": "OPEN",
            },
            final_review={"eligible": False, "reason": "Description is unrelated"},
        )

        review.assert_awaited_once()
        self.assertEqual(update.call_args.kwargs["status"], "DISCARDED")
        self.assertEqual(update.call_args.kwargs["discard_reason"], "LLM_FINAL_REJECTED")
        self.assertEqual(update.call_args.kwargs["ai_reason"], "Description is unrelated")
        self.assertEqual(update.call_args.kwargs["ai_status"], "PROCESSED")

    def test_page_not_found_is_marked_processed(self) -> None:
        _, update = self.run_validation(
            {
                "id": 28,
                "source_url": "https://example.com/job/28",
                "title": "QA Engineer Pleno",
            },
            {"page_not_found": True},
        )

        self.assertEqual(update.call_args.kwargs["status"], "CLOSED")
        self.assertEqual(update.call_args.kwargs["ai_status"], "PROCESSED")

    def test_ollama_failure_leaves_job_pending_for_retry(self) -> None:
        with patch(
            "v2.flows.telegram.validator.review_job_with_ollama",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Ollama unavailable"),
        ) as review:
            with tempfile.TemporaryDirectory() as temp_dir:
                with (
                    patch.object(
                        validator,
                        "get_jobs_for_validation",
                        return_value=[
                            {
                                "id": 27,
                                "source_url": "https://example.com/job/27",
                                "title": "QA Engineer Pleno",
                                "remote": 1,
                            }
                        ],
                    ),
                    patch.object(validator, "async_playwright", return_value=FakePlaywrightContext()),
                    patch.object(validator, "MeuPadrinhoAnalyzer") as analyzer_class,
                    patch.object(validator, "update_job_validation") as update,
                    patch.object(config, "meupadrinho_profile_dir", Path(temp_dir)),
                    patch.object(config, "headless", True),
                    patch.object(config, "timeout_ms", 1000),
                    patch.object(config, "validate_delay_min", 0),
                    patch.object(config, "validate_delay_max", 0),
                    patch.object(validator.random, "uniform", return_value=0),
                ):
                    analyzer_class.return_value.analyze = AsyncMock(
                        return_value={
                            "title": "QA Engineer Pleno",
                            "remote": True,
                            "level": "Pleno",
                            "job_status": "OPEN",
                        }
                    )
                    asyncio.run(validator.run_validator(limit=1))

        review.assert_awaited_once()
        update.assert_not_called()


class TestMeuPadrinhoRemoteExtraction(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = MeuPadrinhoAnalyzer()

    def extract_remote(self, workplace: str) -> bool:
        lines = [
            "Publicado: hoje",
            "QA Engineer Pleno",
            "Example Company",
            "São Paulo",
            workplace,
            "Sobre a vaga",
        ]
        return self.analyzer.extract_header(lines)["remote"]

    def test_remote_mode_is_detected(self) -> None:
        self.assertTrue(self.extract_remote("Remote"))
        self.assertTrue(self.extract_remote("Home office"))

    def test_hybrid_and_onsite_are_not_remote(self) -> None:
        for workplace in ("Híbrido", "Hybrid", "Presencial", "On-site"):
            with self.subTest(workplace=workplace):
                self.assertFalse(self.extract_remote(workplace))

    def test_mixed_remote_and_hybrid_is_not_remote(self) -> None:
        lines = [
            "Publicado: hoje",
            "QA Engineer Pleno",
            "Example Company",
            "São Paulo",
            "Remote",
            "Hybrid",
            "Sobre a vaga",
        ]
        self.assertFalse(self.analyzer.extract_header(lines)["remote"])


if __name__ == "__main__":
    unittest.main()
