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
from urllib.error import URLError

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


class FakeManagedProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = 0
        return self.returncode


class TestDashboardCommandLogs(unittest.TestCase):
    def setUp(self) -> None:
        with server.ACTIVE_PROCESS_LOCK:
            server.ACTIVE_PROCESS = None
            server.CURRENT_COMMAND = None
        with server.OLLAMA_PROCESS_LOCK:
            server.OLLAMA_PROCESS = None
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

    def test_command_completion_refreshes_dashboard_stats(self) -> None:
        self.assertIn("let commandNeedsStatsRefresh = false;", server.PAGE_HTML)
        self.assertIn("commandNeedsStatsRefresh = true;", server.PAGE_HTML)
        self.assertIn(
            "if (commandNeedsStatsRefresh) {\n"
            "            commandNeedsStatsRefresh = false;\n"
            "            await refreshStats();\n"
            "          }",
            server.PAGE_HTML,
        )

    def test_dashboard_has_disabled_connect_to_recruiters_button(self) -> None:
        self.assertIn(
            '<button class="secondary" disabled title="Coming soon">Connect to Recruiters</button>',
            server.PAGE_HTML,
        )

    def test_dashboard_exposes_ollama_status_and_start_control(self) -> None:
        self.assertIn('id="ollama-status"', server.PAGE_HTML)
        self.assertIn("ollama-online", server.PAGE_HTML)
        self.assertIn("ollama-offline", server.PAGE_HTML)
        self.assertIn('id="ollama-start"', server.PAGE_HTML)
        self.assertIn('fetch("/api/ollama/status")', server.PAGE_HTML)
        self.assertIn('fetch("/api/ollama/start"', server.PAGE_HTML)

    def test_dashboard_has_close_control_and_fallback(self) -> None:
        self.assertIn('id="close-dashboard"', server.PAGE_HTML)
        self.assertIn('fetch("/api/close"', server.PAGE_HTML)
        self.assertIn("window.close()", server.PAGE_HTML)
        self.assertIn("Dashboard stopped. You can close this tab.", server.PAGE_HTML)

    def test_dashboard_and_companies_pages_are_separate(self) -> None:
        self.assertIn('href="/companies">Companies</a>', server.PAGE_HTML)
        self.assertNotIn("import-modal", server.PAGE_HTML)
        self.assertIn('href="/">Dashboard</a>', server.COMPANIES_PAGE_HTML)
        self.assertIn('id="add-company-form"', server.COMPANIES_PAGE_HTML)
        self.assertIn('fetch("/api/companies")', server.COMPANIES_PAGE_HTML)

    def test_pages_use_shared_stylesheet_and_header_component(self) -> None:
        for page in (server.PAGE_HTML, server.COMPANIES_PAGE_HTML):
            self.assertIn('href="/style/dashboard.css"', page)
            self.assertNotIn("<style>", page)
            self.assertIn('class="site-header"', page)

    def test_ollama_status_reports_api_unavailability(self) -> None:
        with patch.object(server, "urlopen", side_effect=URLError("offline")):
            self.assertFalse(server.is_ollama_running())

    def test_start_ollama_launches_detached_service_when_offline(self) -> None:
        with (
            patch.object(server, "is_ollama_running", side_effect=[False, False]),
            patch.object(server.shutil, "which", return_value="C:\\Ollama\\ollama.exe"),
            patch.object(server.subprocess, "Popen") as popen,
        ):
            succeeded, started, error = server.start_ollama()

        self.assertTrue(succeeded)
        self.assertTrue(started)
        self.assertIsNone(error)
        self.assertEqual(popen.call_args.args[0], ["C:\\Ollama\\ollama.exe", "serve"])
        self.assertEqual(popen.call_args.kwargs["stdin"], server.subprocess.DEVNULL)
        self.assertEqual(popen.call_args.kwargs["stdout"], server.subprocess.DEVNULL)
        self.assertEqual(popen.call_args.kwargs["stderr"], server.subprocess.DEVNULL)

    def test_close_stops_only_dashboard_owned_ollama(self) -> None:
        process = FakeManagedProcess()
        server.OLLAMA_PROCESS = process
        self.addCleanup(setattr, server, "OLLAMA_PROCESS", None)

        succeeded, error = server.stop_dashboard_ollama()

        self.assertTrue(succeeded)
        self.assertIsNone(error)
        self.assertTrue(process.terminated)
        self.assertIsNone(server.OLLAMA_PROCESS)

    def test_close_leaves_external_ollama_unmanaged(self) -> None:
        server.OLLAMA_PROCESS = None

        with patch.object(server, "stop_external_ollama", return_value=(True, None)) as stop:
            succeeded, error = server.stop_dashboard_ollama()

        self.assertTrue(succeeded)
        self.assertIsNone(error)
        self.assertIsNone(server.OLLAMA_PROCESS)
        stop.assert_called_once_with()

    def test_close_stops_external_ollama_listener_by_pid(self) -> None:
        query = server.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='[{"Id":5184,"Name":"ollama"}]',
            stderr="",
        )
        stopped = server.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )
        with (
            patch.object(server.sys, "platform", "win32"),
            patch.object(server.shutil, "which", return_value="powershell.exe"),
            patch.object(server.subprocess, "run", side_effect=[query, stopped]) as run,
        ):
            succeeded, error = server.stop_external_ollama()

        self.assertTrue(succeeded)
        self.assertIsNone(error)
        self.assertEqual(run.call_count, 2)
        self.assertIn("Get-NetTCPConnection -LocalPort 11434", run.call_args_list[0].args[0][-1])
        self.assertIn("Get-Process -Id 5184", run.call_args_list[1].args[0][-1])

    def test_close_does_not_stop_a_different_listener_on_ollama_port(self) -> None:
        query = server.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='[{"Id":4321,"Name":"python"}]',
            stderr="",
        )
        with (
            patch.object(server.sys, "platform", "win32"),
            patch.object(server.shutil, "which", return_value="powershell.exe"),
            patch.object(server.subprocess, "run", return_value=query) as run,
        ):
            succeeded, error = server.stop_external_ollama()

        self.assertFalse(succeeded)
        self.assertIn("not Ollama", error)
        run.assert_called_once()

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
        self.assertIn("This careers website is already registered.", server.COMPANIES_PAGE_HTML)
        self.assertIn("Company added successfully.", server.COMPANIES_PAGE_HTML)

    def test_companies_page_and_list_endpoint(self) -> None:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.DashboardHandler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        with patch.object(server, "get_career_sources", return_value=[
            {
                "id": 1,
                "company": "Example",
                "careers_url": "https://example.com/careers",
                "search_url": None,
                "active": 1,
            }
        ]) as get_sources:
            with urlopen(f"http://127.0.0.1:{httpd.server_port}/companies") as response:
                page = response.read().decode("utf-8")
            with urlopen(f"http://127.0.0.1:{httpd.server_port}/style/dashboard.css") as response:
                stylesheet = response.read().decode("utf-8")
                stylesheet_content_type = response.headers["Content-Type"]
            with urlopen(f"http://127.0.0.1:{httpd.server_port}/api/companies") as response:
                companies = json.load(response)

        self.assertIn("Add Company Career Page", page)
        self.assertIn(".site-header", stylesheet)
        self.assertEqual(stylesheet_content_type, "text/css; charset=utf-8")
        self.assertEqual(len(companies["companies"]), 1)
        self.assertEqual(companies["companies"][0]["company"], "Example")
        get_sources.assert_called_once_with()

    def test_ollama_status_and_start_endpoints(self) -> None:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.DashboardHandler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        with (
            patch.object(server, "is_ollama_running", return_value=False),
            patch.object(server, "start_ollama", return_value=(True, True, None)),
        ):
            with urlopen(f"http://127.0.0.1:{httpd.server_port}/api/ollama/status") as response:
                status = json.load(response)

            request = Request(
                f"http://127.0.0.1:{httpd.server_port}/api/ollama/start",
                method="POST",
            )
            with urlopen(request) as response:
                start = json.load(response)

        self.assertEqual(status, {"running": False})
        self.assertEqual(start, {"started": True, "error": None})

    def test_close_endpoint_stops_owned_services_then_shuts_down_server(self) -> None:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.DashboardHandler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        with (
            patch.object(server, "stop_dashboard_ollama", return_value=(True, None)) as stop_ollama,
            patch.object(server, "stop_active_command", return_value=(True, None)) as stop_command,
            patch.object(server, "request_server_shutdown") as shutdown,
        ):
            request = Request(
                f"http://127.0.0.1:{httpd.server_port}/api/close",
                method="POST",
            )
            with urlopen(request) as response:
                result = json.load(response)

        self.assertEqual(result, {"closed": True})
        stop_ollama.assert_called_once_with()
        stop_command.assert_called_once_with()
        shutdown.assert_called_once_with(httpd)


if __name__ == "__main__":
    unittest.main()
