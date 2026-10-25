"""Unit tests for dashboard command output handling."""

from __future__ import annotations

import io
import json
import time
import unittest
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen
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

    def test_dashboard_has_continue_buttons_for_both_review_flows(self) -> None:
        self.assertEqual(server.PAGE_HTML.count("Continue (next 10)"), 2)
        self.assertIn("triggerCommand(['telegram', 'open'], 'Continue Telegram review')", server.PAGE_HTML)
        self.assertIn("triggerCommand(['careers', 'open'], 'Continue career review')", server.PAGE_HTML)
        self.assertIn('value="gupy"> Gupy Only', server.PAGE_HTML)

    def test_dashboard_has_disabled_connect_to_recruiters_button(self) -> None:
        self.assertIn(
            '<button class="secondary" disabled title="Coming soon">Connect to Recruiters</button>',
            server.PAGE_HTML,
        )

    def test_import_career_reports_success_and_duplicate(self) -> None:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.DashboardHandler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        with patch.object(server, "insert_career_source", side_effect=[123, 0]) as insert:
            responses = []
            for _ in range(2):
                request = Request(
                    f"http://127.0.0.1:{httpd.server_port}/api/import-career",
                    data=json.dumps({
                        "company": "Example",
                        "careers_url": "https://example.com/careers",
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request) as response:
                    responses.append(json.load(response))

        self.assertEqual(
            responses,
            [{"ok": True, "duplicate": False}, {"ok": True, "duplicate": True}],
        )
        self.assertEqual(insert.call_count, 2)
        self.assertIn('id="snackbar"', server.PAGE_HTML)
        self.assertIn("Website already registered.", server.PAGE_HTML)
        self.assertIn("Career source added successfully.", server.PAGE_HTML)


if __name__ == "__main__":
    unittest.main()
