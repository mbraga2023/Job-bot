"""Tests for LLM-assisted QA job-title classification."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from v2.core.qa_classifier import is_qa_title


class TestQaTitleClassifier(unittest.IsolatedAsyncioTestCase):
    async def test_excluded_title_does_not_call_ollama(self) -> None:
        with patch(
            "v2.core.qa_classifier._classify_with_ollama",
            new_callable=AsyncMock,
        ) as classify:
            self.assertFalse(await is_qa_title("Analista de Controle de Qualidade Pleno"))

        classify.assert_not_awaited()

    async def test_qa_candidate_uses_ollama_result(self) -> None:
        with patch(
            "v2.core.qa_classifier._classify_with_ollama",
            new_callable=AsyncMock,
            return_value=False,
        ) as classify:
            self.assertFalse(await is_qa_title("QA Engineer"))

        classify.assert_awaited_once_with("QA Engineer")

    async def test_ollama_failure_falls_back_to_title_rules(self) -> None:
        with patch(
            "v2.core.qa_classifier._classify_with_ollama",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Ollama unavailable"),
        ):
            self.assertTrue(await is_qa_title("QA Engineer"))


if __name__ == "__main__":
    unittest.main()
