import unittest
from unittest.mock import MagicMock
import asyncio

from agents.analyzers.meupadrinho import MeuPadrinhoAnalyzer
import config


class RateLimitAndVpnTests(unittest.TestCase):

    def test_config_pacing_constants_exist(self):
        self.assertTrue(hasattr(config, "VALIDATION_LIMIT"))
        self.assertEqual(config.VALIDATION_LIMIT, 50)
        self.assertTrue(hasattr(config, "VALIDATE_DELAY_MIN"))
        self.assertTrue(hasattr(config, "VALIDATE_DELAY_MAX"))
        self.assertGreater(config.VALIDATE_DELAY_MIN, 0)
        self.assertGreaterEqual(config.VALIDATE_DELAY_MAX, config.VALIDATE_DELAY_MIN)

    def test_meupadrinho_analyzer_detects_http_429_status(self):
        analyzer = MeuPadrinhoAnalyzer()

        fake_page = MagicMock()
        fake_response = MagicMock()
        fake_response.status = 429
        fake_page.last_response = fake_response

        # is_rate_limited with status 429
        self.assertTrue(analyzer.is_rate_limited(fake_page, []))

        # analyze returns rate_limited flag immediately
        result = asyncio.run(analyzer.analyze(fake_page))
        self.assertTrue(result.get("rate_limited"))
        self.assertEqual(result.get("status_code"), 429)
        self.assertFalse(result.get("page_not_found"))

    def test_meupadrinho_analyzer_detects_rate_limit_body_text(self):
        analyzer = MeuPadrinhoAnalyzer()

        fake_page = MagicMock()
        fake_page.last_response = None

        lines = [
            "Erro",
            "Muitas requisições enviadas recentemente.",
            "Acesso bloqueado temporariamente.",
        ]

        self.assertTrue(analyzer.is_rate_limited(fake_page, lines))

    def test_meupadrinho_analyzer_not_rate_limited_on_normal_page(self):
        analyzer = MeuPadrinhoAnalyzer()

        fake_page = MagicMock()
        fake_response = MagicMock()
        fake_response.status = 200
        fake_page.last_response = fake_response

        lines = [
            "Sobre a vaga",
            "Analista de QA",
            "Tecnologias",
            "Playwright",
        ]

        self.assertFalse(analyzer.is_rate_limited(fake_page, lines))


if __name__ == "__main__":
    unittest.main()
