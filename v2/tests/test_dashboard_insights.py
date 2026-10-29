"""Tests for repository-backed dashboard insights."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from v2.dashboard import insights


class TestRepositoryInsights(unittest.TestCase):
    def test_test_coverage_runs_instrumented_v2_suite_and_parses_measurement(self) -> None:
        payload = {
            "coverage_percent": 45.0,
            "covered_lines": 1101,
            "total_lines": 2448,
            "tests_run": 105,
            "test_failures": 1,
            "test_errors": 0,
            "test_issues": [
                {"test": "test.module.Case.test_name", "kind": "failure", "detail": "AssertionError"}
            ],
            "generated_at": "2026-10-29T20:00-03:00",
        }
        result = subprocess.CompletedProcess(
            args=["python", "-c"],
            returncode=0,
            stdout=f"diagnostic line\n{json.dumps(payload)}\n",
            stderr="",
        )

        with patch.object(insights.subprocess, "run", return_value=result) as run:
            data = insights.get_test_coverage()

        self.assertEqual(data, payload)
        self.assertEqual(run.call_args.args[0][:2], [insights.sys.executable, "-c"])
        self.assertEqual(run.call_args.kwargs["timeout"], 180)

    def test_insights_aggregate_actual_code_changes_and_existing_tests(self) -> None:
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        output = (
            f"{today}\t{'a' * 40}\0"
            "v2/core/database.py\0"
            "v2/tests/test_database.py\0"
            f"{yesterday}\t{'b' * 40}\0"
            "v2/dashboard/server.py\0"
            "v2/README.md\0"
        )
        result = subprocess.CompletedProcess(args=["git"], returncode=0, stdout=output, stderr="")

        with tempfile.TemporaryDirectory() as directory:
            test_directory = Path(directory)
            (test_directory / "test_database.py").touch()
            (test_directory / "test_dashboard.py").touch()
            with (
                patch.object(insights.subprocess, "run", return_value=result) as run,
                patch.object(insights, "TEST_DIRECTORY", test_directory),
            ):
                data = insights.get_repository_test_insights(7)

        self.assertEqual(data["summary"], {"commits": 2, "files_changed": 2})
        core = next(module for module in data["modules"] if module["id"] == "core")
        dashboard = next(module for module in data["modules"] if module["id"] == "dashboard")
        self.assertEqual(core["commits"], 1)
        self.assertEqual(core["files_changed"], 1)
        self.assertEqual(core["test_files"], ["test_database.py"])
        self.assertEqual(dashboard["commits"], 1)
        self.assertEqual(dashboard["test_files"], ["test_dashboard.py"])
        self.assertEqual(sum(point["commits"] for point in data["trend"]), 2)
        self.assertEqual(run.call_args.args[0][0:2], ["git", "log"])

    def test_insights_reject_unsupported_period_without_running_git(self) -> None:
        with patch.object(insights.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "7, 30, or 90"):
                insights.get_repository_test_insights(14)

        run.assert_not_called()

    def test_git_failure_is_not_reported_as_empty_insights(self) -> None:
        with patch.object(
            insights.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(128, ["git", "log"], stderr="not a repository"),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                insights.get_repository_test_insights(7)
