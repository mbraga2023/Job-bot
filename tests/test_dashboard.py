import json
import tempfile
import threading
import unittest
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

    def test_dashboard_page_has_all_requested_actions(self):
        with urlopen(self.url + "/") as response:
            page = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        for name in COMMANDS:
            self.assertIn(f'data-command="{name}"', page)

    def test_open_action_maps_to_existing_open_jobs_command(self):
        self.assertEqual(COMMANDS["open"], "open-jobs")

    def test_open_action_launches_cli_and_captures_output(self):
        class FakeProcess:
            stdout = ["opened jobs\n"]
            returncode = 0

            def wait(self):
                return self.returncode

        controller = DashboardController()
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
        self.assertEqual(controller.state()["return_code"], 0)
        self.assertIn("opened jobs", controller.state()["output"])

    def test_child_command_captures_unicode_output(self):
        controller = DashboardController()
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
