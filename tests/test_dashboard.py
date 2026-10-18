import json
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from commands.dashboard import (
    COMMANDS,
    PROJECT_ROOT,
    DashboardController,
    _make_handler,
)
from database.career_sources import insert_career_sources


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.controller = DashboardController()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _make_handler(self.controller),
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.controller.close()

    def test_dashboard_page_has_all_requested_actions(self):
        with urlopen(self.url + "/") as response:
            page = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        for name in COMMANDS:
            self.assertIn(f'data-command="{name}"', page)

    def test_open_action_maps_to_existing_open_jobs_command(self):
        self.assertEqual(COMMANDS["open"], "open-jobs")
        self.assertEqual(COMMANDS["open-career"], "open-career-jobs")
        self.assertEqual(COMMANDS["careers"], "careers")
        self.assertEqual(
            COMMANDS["validate-career-jobs"],
            "validate-career-jobs",
        )

    def test_open_action_launches_cli_and_captures_output(self):
        class FakeProcess:
            stdout = ["opened jobs\n"]
            returncode = 0

            def wait(self):
                return self.returncode

        controller = DashboardController()
        self.addCleanup(controller.close)
        with patch(
            "commands.dashboard.subprocess.Popen",
            return_value=FakeProcess(),
        ) as popen:
            controller._run_command("open")

        args, options = popen.call_args
        self.assertEqual(args[0][-1], "open-jobs")
        self.assertEqual(options["cwd"], PROJECT_ROOT)
        self.assertEqual(options["env"]["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(options["env"]["PYTHONUTF8"], "1")
        self.assertFalse(controller.state()["running"])
        self.assertFalse(controller.state()["stopped"])
        self.assertEqual(controller.state()["return_code"], 0)
        self.assertIn("opened jobs", controller.state()["output"])

    def test_dashboard_page_groups_flows_and_has_stop_button(self):
        with urlopen(self.url + "/") as response:
            page = response.read().decode("utf-8")

        telegram_group = page.index('id="telegram-linkedin-flow"')
        career_group = page.index('id="career-flow"')
        self.assertLess(telegram_group, career_group)
        telegram_markup = page[telegram_group:career_group]
        career_markup = page[career_group:page.index('id="status"')]
        self.assertIn('data-command="collect"', telegram_markup)
        self.assertIn('data-command="validate"', telegram_markup)
        self.assertIn('data-command="linkedin"', telegram_markup)
        self.assertIn('data-command="open"', telegram_markup)
        self.assertIn('data-command="careers"', career_markup)
        self.assertIn('data-command="open-career"', career_markup)
        self.assertIn('data-command="validate-career-jobs"', career_markup)
        self.assertIn('id="stop-command"', page)
        self.assertIn('fetch("/api/stop"', page)

    def test_dashboard_page_has_single_and_batch_career_source_forms(self):
        with urlopen(self.url + "/") as response:
            page = response.read().decode("utf-8")

        self.assertIn('id="career-source-form"', page)
        self.assertIn('id="show-career-source-form"', page)
        self.assertIn('name="company"', page)
        self.assertIn('name="careers_url"', page)
        self.assertIn('name="search_url"', page)
        self.assertIn('id="career-source-batch-form"', page)
        self.assertIn('accept=".json,application/json"', page)

    def test_career_source_endpoint_saves_a_single_source(self):
        payload = {
            "sources": [
                {
                    "company": "  Example Co  ",
                    "careers_url": " https://example.com/jobs ",
                    "search_url": " ",
                }
            ]
        }
        with patch(
            "commands.dashboard.insert_career_sources",
            return_value=(1, 0),
        ) as insert_sources:
            request = Request(
                self.url + "/api/career-sources",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertEqual(result, {"inserted": 1, "skipped": 0})
        insert_sources.assert_called_once_with(
            [
                {
                    "company": "Example Co",
                    "careers_url": "https://example.com/jobs",
                    "search_url": None,
                }
            ]
        )

    def test_career_source_endpoint_accepts_batch_sources(self):
        sources = [
            {
                "company": "First Co",
                "careers_url": "https://first.example/jobs",
            },
            {
                "company": "Second Co",
                "careers_url": "https://second.example/jobs",
                "search_url": "https://second.example/jobs?query=qa",
            },
        ]
        with patch(
            "commands.dashboard.insert_career_sources",
            return_value=(2, 0),
        ) as insert_sources:
            request = Request(
                self.url + "/api/career-sources",
                data=json.dumps({"sources": sources}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read())

        self.assertEqual(result, {"inserted": 2, "skipped": 0})
        insert_sources.assert_called_once_with(
            [
                {
                    "company": "First Co",
                    "careers_url": "https://first.example/jobs",
                    "search_url": None,
                },
                sources[1],
            ]
        )

    def test_career_source_endpoint_rejects_invalid_batch_before_saving(self):
        payload = {
            "sources": [
                {
                    "company": "Valid Co",
                    "careers_url": "https://valid.example/jobs",
                },
                {
                    "company": "Invalid Co",
                    "careers_url": "ftp://invalid.example/jobs",
                },
            ]
        }
        with patch("commands.dashboard.insert_career_sources") as insert_sources:
            request = Request(
                self.url + "/api/career-sources",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as error:
                urlopen(request)

        self.assertEqual(error.exception.code, 400)
        insert_sources.assert_not_called()

    def test_database_saves_career_sources_and_skips_duplicate_urls(self):
        sources = [
            {
                "company": "Example Co",
                "careers_url": "https://example.com/jobs",
                "search_url": None,
            },
            {
                "company": "Duplicate Co",
                "careers_url": "https://example.com/jobs",
                "search_url": "https://example.com/jobs?qa",
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "career_sources.db"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE career_sources (
                        company TEXT NOT NULL,
                        careers_url TEXT NOT NULL UNIQUE,
                        search_url TEXT,
                        source_type TEXT,
                        active INTEGER
                    )
                    """
                )
                connection.commit()
            finally:
                connection.close()

            @contextmanager
            def open_connection():
                connection = sqlite3.connect(database_path)
                try:
                    yield connection
                finally:
                    connection.close()

            with patch(
                "database.career_sources.get_connection",
                side_effect=open_connection,
            ):
                result = insert_career_sources(sources)

            connection = sqlite3.connect(database_path)
            try:
                rows = connection.execute(
                    """
                    SELECT company, careers_url, search_url
                    FROM career_sources
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(result, (1, 1))
        self.assertEqual(
            rows,
            [("Example Co", "https://example.com/jobs", None)],
        )

    def test_stop_command_terminates_running_child(self):
        class FakeProcess:
            def __init__(self):
                self.terminated = False

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

        process = FakeProcess()
        self.controller._state.update(running=True, command="collect")
        self.controller._process = process

        self.assertTrue(self.controller.stop_command())
        self.assertTrue(process.terminated)
        self.assertTrue(self.controller.state()["stopping"])

    def test_stop_command_covers_process_startup_race(self):
        spawn_started = threading.Event()
        allow_spawn = threading.Event()

        class FakeProcess:
            stdout = ()
            returncode = -15
            terminated = False

            def poll(self):
                return 0 if self.terminated else None

            def terminate(self):
                self.terminated = True

            def wait(self):
                return self.returncode

        process = FakeProcess()

        def fake_popen(*args, **kwargs):
            spawn_started.set()
            if not allow_spawn.wait(timeout=2):
                raise TimeoutError("Test did not release process startup.")
            return process

        with patch("commands.dashboard.subprocess.Popen", side_effect=fake_popen):
            self.assertTrue(self.controller.start_command("collect"))
            self.assertTrue(spawn_started.wait(timeout=2))
            self.assertTrue(self.controller.stop_command())
            allow_spawn.set()

            deadline = time.monotonic() + 3
            while self.controller.state()["running"] and time.monotonic() < deadline:
                time.sleep(0.01)

        self.assertTrue(process.terminated)
        self.assertFalse(self.controller.state()["running"])
        self.assertTrue(self.controller.state()["stopped"])

    def test_stop_endpoint_requests_termination(self):
        self.controller._state.update(running=True, command="collect")
        with patch.object(
            self.controller,
            "stop_command",
            return_value=True,
        ) as stop_command:
            request = Request(
                self.url + "/api/stop",
                data=b"",
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read())

        self.assertEqual(response.status, 202)
        self.assertEqual(result, {"stopping": True})
        stop_command.assert_called_once_with()

    def test_child_command_captures_unicode_output(self):
        controller = DashboardController()
        self.addCleanup(controller.close)
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(temp_dir) / "print_unicode.py"
            script.write_text("print('🚀 Starting')\n", encoding="utf-8")
            with patch("commands.dashboard.MAIN_SCRIPT", script):
                controller._run_command("collect")

        self.assertEqual(controller.state()["return_code"], 0)
        self.assertIn("🚀 Starting", controller.state()["output"])

    def test_dashboard_page_has_copy_logs_button(self):
        with urlopen(self.url + "/") as response:
            page = response.read().decode("utf-8")

        self.assertIn('id="copy-logs"', page)
        self.assertIn("navigator.clipboard.writeText(output.textContent)", page)

    def test_dashboard_page_has_export_logs_button(self):
        with urlopen(self.url + "/") as response:
            page = response.read().decode("utf-8")

        self.assertIn('id="export-logs"', page)
        self.assertIn('fetch("/api/logs"', page)
        self.assertIn('link.download = "job-bot-logs.txt"', page)

    def test_export_logs_endpoint_returns_complete_output_as_text_file(self):
        output = "x" * 100_050
        self.controller._state["command"] = "validate"
        self.controller._append_output(output)

        with urlopen(self.url + "/api/logs") as response:
            exported = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers.get_content_type(), "text/plain")
        self.assertEqual(
            response.headers["Content-Disposition"],
            'attachment; filename="job-bot-validate-logs.txt"',
        )
        self.assertEqual(len(exported), len(output))
        self.assertEqual(exported, output)
        self.assertEqual(len(self.controller.state()["output"]), 100_000)

    def test_export_logs_endpoint_reports_when_no_logs_exist(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + "/api/logs")

        self.assertEqual(error.exception.code, 404)

    def test_run_endpoint_starts_allowlisted_command(self):
        with patch.object(
            self.controller,
            "start_command",
            return_value=True,
        ) as start_command:
            request = Request(
                self.url + "/api/run",
                data=json.dumps({"command": "linkedin"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read())

        self.assertEqual(response.status, 202)
        self.assertEqual(result, {"started": "linkedin"})
        start_command.assert_called_once_with("linkedin")

    def test_run_endpoint_rejects_unknown_action(self):
        with patch.object(self.controller, "start_command") as start_command:
            request = Request(
                self.url + "/api/run",
                data=json.dumps({"command": "delete"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as error:
                urlopen(request)

        self.assertEqual(error.exception.code, 400)
        start_command.assert_not_called()

    def test_run_endpoint_rejects_non_string_action(self):
        request = Request(
            self.url + "/api/run",
            data=json.dumps({"command": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request)

        self.assertEqual(error.exception.code, 400)

if __name__ == "__main__":
    unittest.main()
