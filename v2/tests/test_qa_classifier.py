"""Tests for final Ollama job review."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from v2.core.qa_classifier import review_job_with_ollama


class TestOllamaJobReview(unittest.IsolatedAsyncioTestCase):
    async def test_final_review_receives_all_job_context_and_exclusions(self) -> None:
        client = Mock()
        client.chat = AsyncMock(
            return_value=SimpleNamespace(
                message=SimpleNamespace(
                    content='{"eligible": false, "reason": "Not software QA"}'
                )
            )
        )
        ollama = SimpleNamespace(AsyncClient=Mock(return_value=client))

        with patch.dict("sys.modules", {"ollama": ollama}):
            result = await review_job_with_ollama(
                title="QA Engineer Pleno",
                level="Pleno",
                description="Tests software applications.",
                remote=True,
                technologies=["Selenium", "ISTQB"],
            )

        self.assertEqual(
            result,
            {"eligible": False, "reason": "Not software QA"},
        )
        prompt = client.chat.await_args.kwargs["messages"][0]["content"]
        self.assertIn("QA Engineer Pleno", prompt)
        self.assertIn("Seniority: Pleno", prompt)
        self.assertIn("Remote confirmed: True", prompt)
        self.assertIn("Technologies: Selenium, ISTQB", prompt)
        self.assertIn("strong evidence of QA/testing work", prompt)
        self.assertIn("Tests software applications.", prompt)
        self.assertIn("Monitor de Qualidade", prompt)
        self.assertEqual(client.chat.await_args.kwargs["model"], "qwen2.5-coder:1.5b")

    async def test_invalid_final_review_response_raises(self) -> None:
        client = Mock()
        client.chat = AsyncMock(
            return_value=SimpleNamespace(
                message=SimpleNamespace(content='{"eligible": "yes"}')
            )
        )
        ollama = SimpleNamespace(AsyncClient=Mock(return_value=client))

        with patch.dict("sys.modules", {"ollama": ollama}):
            with self.assertRaisesRegex(ValueError, "invalid final job review"):
                await review_job_with_ollama("QA Engineer", "Pleno", "", True, [])


if __name__ == "__main__":
    unittest.main()
