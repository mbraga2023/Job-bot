"""Unit tests for dashboard command output handling."""

from __future__ import annotations

import io
import time
import unittest
from unittest.mock import patch

from v2.dashboard import server


class FakeProcess:
    def __init__(self, output: str) -> None:
        self.stdout = io.StringIO(output)
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self) -> int:
        self.returncode = 0
        return self.returncode


class TestDashboardCommandLogs(unittest.TestCase):
    def setUp(self) -> None:
        with server.ACTIVE_PROCESS_LOCK:
            server.ACTIVE_PROCESS = None
            server.CURRENT_COMMAND = None
        with server.COMMAND_OUTPUT_LOCK:
            server.COMMAND_OUTPUT.clear()

    def test_output_from_multiple_commands_remains_visible(self) -> None:
        processes = [FakeProcess("first command output\n"), FakeProcess("second command output\n")]

        with patch.object(server.subprocess, "Popen", side_effect=processes) as popen:
            for label in ("First command", "Second command"):
                started = server.run_command_in_background(["stats"], label)
                self.assertTrue(started)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    with server.ACTIVE_PROCESS_LOCK:
                        if server.ACTIVE_PROCESS is None:
                            break
                    time.sleep(0.01)
                else:
                    self.fail(f"{label} did not finish")

        logs = server.get_logs()
        self.assertIn(">> Running: First command", logs)
        self.assertIn("first command output", logs)
        self.assertIn(">> Running: Second command", logs)
        self.assertIn("second command output", logs)
        self.assertEqual(popen.call_args.kwargs["env"]["PYTHONUNBUFFERED"], "1")


if __name__ == "__main__":
    unittest.main()
