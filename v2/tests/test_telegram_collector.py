"""Tests for unfiltered Telegram message collection."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v2.flows.telegram import collector


class FakeTelegramClient:
    def __init__(self, message) -> None:
        self.message = message

    async def start(self) -> None:
        pass

    async def get_entity(self, channel: str) -> str:
        return channel

    def iter_messages(self, channel: str, limit: int):
        async def messages():
            yield self.message

        return messages()

    async def disconnect(self) -> None:
        pass


class TestTelegramCollector(unittest.TestCase):
    def test_collects_non_qa_title_without_filtering(self) -> None:
        message = SimpleNamespace(
            text=(
                "Título: Analista de negócios\n"
                "Empresa: Example\n"
                "Local: Remote\n"
                "https://example.com/job/1"
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config = SimpleNamespace(
                root_dir=Path(temp_dir),
                telegram=SimpleNamespace(
                    session_name="test_session",
                    api_id=1,
                    api_hash="test",
                    channel="test_channel",
                ),
            )
            with (
                patch.object(collector, "config", config),
                patch.object(collector, "TelegramClient", return_value=FakeTelegramClient(message)),
                patch.object(collector, "insert_discovered_job", return_value=1) as insert_job,
            ):
                asyncio.run(collector.run_collector(limit=1))

        self.assertEqual(insert_job.call_args.kwargs["title"], "Analista de negócios")
        self.assertEqual(insert_job.call_args.kwargs["category"], "UNCLASSIFIED")


if __name__ == "__main__":
    unittest.main()
