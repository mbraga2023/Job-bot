"""Tests for deterministic Telegram gates and final Ollama review."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from v2.config import config
from v2.flows.telegram.analyzers.meupadrinho import MeuPadrinhoAnalyzer
from v2.flows.telegram import validator
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


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
                patch.object(
                    validator, "async_playwright", return_value=FakePlaywrightContext()
                ),
                patch.object(validator, "MeuPadrinhoAnalyzer") as analyzer_class,
                patch.object(
                    validator,
                    "review_job_with_ollama",
                    new_callable=AsyncMock,
                    return_value=final_review
                    or {"eligible": True, "reason": "Approved"},
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
        self.assertEqual(
            update.call_args.kwargs["discard_reason"], "LLM_FINAL_REJECTED"
        )
        self.assertEqual(
            update.call_args.kwargs["ai_reason"], "Description is unrelated"
        )
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

    def test_linkedin_person_url_is_marked_recruiter_without_navigation(self) -> None:
        with (
            patch.object(
                validator,
                "get_jobs_for_validation",
                return_value=[
                    {
                        "id": 33,
                        "source_url": "https://mx.linkedin.com/in/ivan-carrillo-solache",
                    }
                ],
            ),
            patch.object(
                validator, "async_playwright", return_value=FakePlaywrightContext()
            ),
            patch.object(validator, "MeuPadrinhoAnalyzer") as analyzer_class,
            patch.object(validator, "update_job_status") as update_status,
            patch.object(validator, "update_job_validation") as update_validation,
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(config, "meupadrinho_profile_dir", Path(temp_dir)),
            patch.object(config, "headless", True),
        ):
            analyzer_class.return_value.analyze = AsyncMock()
            asyncio.run(validator.run_validator(limit=1))

        update_status.assert_called_once_with(33, "RECRUITER")
        analyzer_class.return_value.analyze.assert_not_awaited()
        update_validation.assert_not_called()

    def test_login_required_warns_and_leaves_job_pending(self) -> None:
        with (
            patch("builtins.print") as print_mock,
            patch(
                "v2.flows.telegram.validator.review_job_with_ollama",
                new_callable=AsyncMock,
            ) as review,
            patch.object(
                validator,
                "get_jobs_for_validation",
                return_value=[
                    {
                        "id": 29,
                        "source_url": "https://example.com/job/29",
                        "title": "QA Engineer Pleno",
                        "remote": 1,
                    }
                ],
            ),
            patch.object(
                validator, "async_playwright", return_value=FakePlaywrightContext()
            ),
            patch.object(validator, "MeuPadrinhoAnalyzer") as analyzer_class,
            patch.object(validator, "update_job_validation") as update,
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(config, "meupadrinho_profile_dir", Path(temp_dir)),
            patch.object(config, "headless", True),
            patch.object(config, "timeout_ms", 1000),
        ):
            analyzer_class.return_value.analyze = AsyncMock(
                return_value={"login_required": True}
            )
            asyncio.run(validator.run_validator(limit=1))

        print_mock.assert_any_call(
            " [!] Meu Padrinho appears to require login. Check whether you "
            "need to log in to the website; leaving this job pending."
        )
        review.assert_not_awaited()
        update.assert_not_called()

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
                    patch.object(
                        validator,
                        "async_playwright",
                        return_value=FakePlaywrightContext(),
                    ),
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

    def test_login_page_is_detected_from_url_or_explicit_prompt(self) -> None:
        login_url_page = SimpleNamespace(
            url="https://meupadrinho.com.br/login?next=/vaga/123"
        )
        prompt_page = SimpleNamespace(url="https://meupadrinho.com.br/vaga/123")
        job_page = SimpleNamespace(url="https://meupadrinho.com.br/vaga/123")

        self.assertTrue(self.analyzer.is_login_required(login_url_page, []))
        self.assertTrue(
            self.analyzer.is_login_required(
                prompt_page,
                ["Faça login para continuar"],
            )
        )
        self.assertFalse(
            self.analyzer.is_login_required(
                job_page,
                ["QA Engineer Pleno", "Sobre a vaga"],
            )
        )


class TestMeuPadrinhoAnalyzer(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.analyzer = MeuPadrinhoAnalyzer()

    async def test_analyze_returns_early_for_http_rate_limit(self) -> None:
        page = SimpleNamespace(last_response=SimpleNamespace(status=429))

        result = await self.analyzer.analyze(page)

        self.assertEqual(
            result,
            {"rate_limited": True, "status_code": 429, "page_not_found": False},
        )

    async def test_analyze_classifies_limited_login_and_missing_pages(self) -> None:
        cases = (
            (
                "https://jobs.example/vaga/1",
                ["Too many requests"],
                {"rate_limited": True, "status_code": 503, "page_not_found": False},
            ),
            (
                "https://jobs.example/login",
                ["Faça login para continuar"],
                {"login_required": True, "page_not_found": False},
            ),
            (
                "https://jobs.example/vaga/404",
                ["Página não encontrada"],
                {
                    "page_not_found": True,
                    "published_date": "",
                    "title": "",
                    "company": "",
                    "location": "",
                    "remote": False,
                    "level": "",
                    "contract": "",
                    "job_source": "meupadrinho",
                    "application_url": "",
                    "application_source": "",
                    "description": "",
                    "technologies": [],
                    "requirements": [],
                    "differentials": [],
                    "benefits": [],
                    "job_status": "CLOSED",
                },
            ),
        )
        for url, lines, expected in cases:
            with self.subTest(url=url):
                page = SimpleNamespace(
                    url=url,
                    last_response=SimpleNamespace(status=503),
                )
                with (
                    patch.object(self.analyzer, "wait_for_content", new_callable=AsyncMock),
                    patch.object(self.analyzer, "get_lines", new_callable=AsyncMock, return_value=lines),
                    patch.object(self.analyzer, "get_apply_button", new_callable=AsyncMock) as get_apply,
                ):
                    result = await self.analyzer.analyze(page)

                self.assertEqual(result, expected)
                get_apply.assert_not_awaited()

    async def test_analyze_extracts_open_listing_and_uses_page_url_as_fallback(self) -> None:
        page = SimpleNamespace(
            url="https://jobs.example/vaga/123",
            last_response=SimpleNamespace(status=200),
        )
        lines = [
            "Publicado: hoje",
            "QA Engineer Pleno",
            "Acme",
            "São Paulo",
            "Remote",
            "Pleno",
            "CLT",
            "Greenhouse",
            "Sobre a vaga",
            "Test web applications",
            "Tecnologias",
            "Playwright",
            "Requisitos",
            "Three years of experience",
            "Diferenciais",
            "API testing",
            "Benefícios",
            "Health plan",
        ]
        with (
            patch.object(self.analyzer, "wait_for_content", new_callable=AsyncMock),
            patch.object(self.analyzer, "get_lines", new_callable=AsyncMock, return_value=lines),
            patch.object(self.analyzer, "get_apply_button", new_callable=AsyncMock, return_value=""),
        ):
            result = await self.analyzer.analyze(page)

        self.assertEqual(result["title"], "QA Engineer Pleno")
        self.assertEqual(result["company"], "Acme")
        self.assertTrue(result["remote"])
        self.assertEqual(result["level"], "Pleno")
        self.assertEqual(result["contract"], "CLT")
        self.assertEqual(result["job_source"], "Greenhouse")
        self.assertEqual(result["application_url"], page.url)
        self.assertEqual(result["description"], "Test web applications")
        self.assertEqual(result["technologies"], ["Playwright"])
        self.assertEqual(result["requirements"], ["Three years of experience"])
        self.assertEqual(result["differentials"], ["API testing"])
        self.assertEqual(result["benefits"], ["Health plan"])
        self.assertEqual(result["job_status"], "OPEN")

    async def test_wait_for_content_continues_after_timeouts_and_tries_network_idle(self) -> None:
        locator = MagicMock()
        locator.first.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        page = MagicMock()
        page.wait_for_load_state = AsyncMock(
            side_effect=[
                PlaywrightTimeoutError("domcontentloaded timeout"),
                PlaywrightTimeoutError("networkidle timeout"),
            ]
        )
        page.get_by_text.return_value = locator

        await self.analyzer.wait_for_content(page)

        self.assertEqual(page.wait_for_load_state.await_count, 2)
        self.assertEqual(locator.first.wait_for.await_count, len(self.analyzer.JOB_CONTENT_MARKERS))
        page.wait_for_load_state.assert_any_await("networkidle", timeout=5000)

    async def test_get_lines_cleans_and_drops_empty_body_lines(self) -> None:
        body = MagicMock()
        body.wait_for = AsyncMock()
        body.inner_text = AsyncMock(return_value="  QA   Engineer \n\n  Remote \t role  ")
        page = MagicMock()
        page.locator.return_value = body

        lines = await self.analyzer.get_lines(page)

        self.assertEqual(lines, ["QA Engineer", "Remote role"])
        body.wait_for.assert_awaited_once_with(state="attached")

    async def test_get_apply_button_skips_missing_invisible_and_timed_out_links(self) -> None:
        button = MagicMock()
        button.count = AsyncMock(return_value=2)
        invisible = MagicMock()
        invisible.is_visible = AsyncMock(return_value=False)
        timed_out = MagicMock()
        timed_out.is_visible = AsyncMock(return_value=True)
        timed_out.get_attribute = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        button.nth.side_effect = [invisible, timed_out]
        invisible.get_attribute = AsyncMock()
        link = MagicMock()
        link.count = AsyncMock(return_value=1)
        visible_link = MagicMock()
        visible_link.is_visible = AsyncMock(return_value=True)
        visible_link.get_attribute = AsyncMock(return_value="/apply/123")
        link.nth.return_value = visible_link
        text = MagicMock()
        text.count = AsyncMock(return_value=0)
        page = MagicMock()
        page.get_by_role.side_effect = [button, link]
        page.get_by_text.return_value = text

        application_url = await self.analyzer.get_apply_button(page)

        self.assertEqual(application_url, "/apply/123")
        invisible.get_attribute.assert_not_awaited()
        visible_link.get_attribute.assert_awaited_once_with("href")

    async def test_get_apply_button_returns_empty_when_no_link_has_href(self) -> None:
        empty = MagicMock()
        empty.count = AsyncMock(return_value=0)
        page = MagicMock()
        page.get_by_role.return_value = empty
        page.get_by_text.return_value = empty

        self.assertEqual(await self.analyzer.get_apply_button(page), "")

    def test_header_handles_missing_data_and_conflicting_workplace_modes(self) -> None:
        self.assertEqual(self.analyzer.extract_header(["QA Engineer"])["title"], "")
        self.assertEqual(
            self.analyzer.extract_header(["Publicado: ontem", "Sobre a vaga"])["title"],
            "",
        )
        header = self.analyzer.extract_header([
            "Publicado: ontem",
            "QA Engineer",
            "•",
            "Acme",
            "São Paulo",
            "Remote",
            "Hybrid",
            "Senior",
            "PJ",
            "LinkedIn",
            "Sobre a vaga",
        ])

        self.assertEqual(header["published_date"], "ontem")
        self.assertEqual(header["company"], "Acme")
        self.assertEqual(header["location"], "São Paulo")
        self.assertFalse(header["remote"])
        self.assertEqual(header["level"], "Senior")
        self.assertEqual(header["contract"], "PJ")
        self.assertEqual(header["job_source"], "LinkedIn")

    def test_description_and_sections_stop_at_next_heading(self) -> None:
        lines = [
            "Sobre a vaga",
            "Build test automation",
            "Tecnologias",
            "Playwright",
            "Requisitos",
            "API testing",
        ]

        self.assertEqual(self.analyzer.extract_description(["QA Engineer"]), "")
        self.assertEqual(self.analyzer.extract_section(lines, "Diferenciais"), [])
        self.assertEqual(self.analyzer.extract_description(lines), "Build test automation")
        self.assertEqual(self.analyzer.extract_section(lines, "Tecnologias"), ["Playwright"])


if __name__ == "__main__":
    unittest.main()
