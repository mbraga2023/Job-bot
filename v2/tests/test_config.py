"""Unit Tests for Decoupled Configuration."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from v2.config import AppConfig


class TestConfig(unittest.TestCase):
    def test_app_config_does_not_require_telegram_env(self):
        # Even if Telegram env vars are completely stripped, AppConfig instantiates fine
        with patch.dict(os.environ, {}, clear=True):
            cfg = AppConfig()
            self.assertTrue(cfg.headless)
            self.assertEqual(cfg.ollama_model, "qwen2.5-coder:1.5b")
            self.assertIsNotNone(cfg.db_path)

            # Accessing telegram property throws only upon attribute access
            with self.assertRaises(RuntimeError) as ctx:
                _ = cfg.telegram.api_id
            self.assertIn("API_ID", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
