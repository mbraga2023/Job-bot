"""Tests for repository-backed dashboard insights."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from io import BytesIO
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v2.dashboard import insights


class TestRepositoryInsights(unittest.TestCase):
    def passing_scenario_outcomes(self) -> dict[str, str]:
        outcomes = {}
        for scenarios in insights.SCENARIO_CATALOG.values():
            for scenario in scenarios:
                for test_case in scenario["test_cases"]:
                    filename, method = test_case.split("::")
                    module_name = Path(filename).stem
                    test_id = f"v2.tests.{module_name}.TestScenarios.{method}"
                    outcomes[test_id] = "passed"
        return outcomes

    def test_test_coverage_parses_line_and_branch_report(self) -> None:
        payload = {
            "coverage_percent": 45.0,
            "line_coverage_percent": 45.0,
            "covered_lines": 1101,
            "total_lines": 2448,
            "branch_coverage_percent": 36.0,
            "covered_branches": 90,
            "total_branches": 250,
            "coverage_tool": "coverage.py",
            "coverage_tool_version": "7.17.0",
            "flows": [
                {
                    "id": "careers",
                    "name": "Fluxo de carreiras",
                    "covered_lines": 240,
                    "total_lines": 500,
                    "coverage_percent": 48.0,
                    "covered_branches": 20,
                    "total_branches": 50,
                    "branch_coverage_percent": 40.0,
                    "files": [
                        {
                            "path": "v2/flows/careers/scanner.py",
                            "covered_lines": 120,
                            "total_lines": 300,
                            "coverage_percent": 40.0,
                            "covered_branches": 10,
                            "total_branches": 20,
                            "branch_coverage_percent": 50.0,
                        }
                    ],
                },
                {
                    "id": "telegram",
                    "name": "Telegram e LinkedIn",
                    "covered_lines": 100,
                    "total_lines": 200,
                    "coverage_percent": 50.0,
                    "covered_branches": 30,
                    "total_branches": 70,
                    "branch_coverage_percent": 42.9,
                    "files": [],
                },
            ],
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
        self.assertIn("branch=True", insights.COVERAGE_RUNNER)
        self.assertIn("coverage.Coverage", insights.COVERAGE_RUNNER)
        self.assertIn("test_outcomes", insights.COVERAGE_RUNNER)

    def test_illustrative_scenario_coverage_formula_equals_78_percent(self) -> None:
        modules = [
            {"risk_weight_raw": 50, "scenario_coverage": 0.8},
            {"risk_weight_raw": 30, "scenario_coverage": 0.6},
            {"risk_weight_raw": 20, "scenario_coverage": 1.0},
        ]

        self.assertEqual(insights._weighted_scenario_percentage(modules), 78.0)

    def test_scenario_coverage_uses_passed_catalog_scenarios_and_normalized_risk(self) -> None:
        outcomes = self.passing_scenario_outcomes()
        outcomes["v2.tests.test_date_utils.TestScenarios.test_normalize_portuguese_date"] = "failed"
        module_activity = [
            {"id": module["id"], "commits": 2 if module["id"] == "core" else 0}
            for module in insights.MODULES
        ]
        defect_history = {
            "status": "available",
            "files": {
                "v2/core/database.py": {
                    "defect_count": 1,
                    "severity_weighted_defects": 3,
                }
            },
        }

        data = insights.calculate_risk_weighted_scenario_coverage(
            outcomes,
            module_activity,
            defect_history,
            tests_run=114,
            git_data_available=True,
        )

        self.assertEqual(data["status"], "available")
        self.assertEqual(data["modules"][0]["scenario_coverage_percent"], 83.3)
        self.assertEqual(data["modules"][0]["risk_weight_raw"], 6)
        self.assertEqual(data["modules"][0]["risk_weight"], 0.666667)
        self.assertEqual(data["coverage_percent"], 88.9)
        self.assertEqual(sum(module["risk_weight"] for module in data["modules"]), 1.0)
        self.assertNotIn("mapped GitHub defect history", data["missing_risk_inputs"])

    def test_unknown_scenario_coverage_is_not_treated_as_full_coverage(self) -> None:
        data = insights.calculate_risk_weighted_scenario_coverage(
            {},
            [{"id": module["id"], "commits": 1} for module in insights.MODULES],
            {"status": "available", "files": {}},
            tests_run=0,
            git_data_available=True,
        )

        self.assertEqual(data["status"], "unavailable")
        self.assertIsNone(data["coverage_percent"])
        self.assertEqual(data["unmeasured_modules"], len(insights.SCENARIO_CATALOG))
        self.assertTrue(all(
            module["scenario_coverage_percent"] is None
            for module in data["excluded_modules"]
        ))

    def test_file_attention_remains_separate_from_scenario_coverage(self) -> None:
        flows = [{
            "id": "careers",
            "files": [
                {"path": "v2/flows/careers/a.py", "covered_lines": 50, "total_lines": 100},
                {"path": "v2/flows/careers/empty.py", "covered_lines": 0, "total_lines": 0},
            ],
        }]
        modules = [{
            "id": "careers",
            "file_commits": {"v2/flows/careers/a.py": 1},
        }]

        insights.annotate_file_attention(flows, modules)

        self.assertEqual(flows[0]["files"][0]["heuristic_risk_score"], 100.0)
        self.assertNotIn("heuristic_risk_score", flows[0]["files"][1])

    def test_github_defect_history_maps_bug_issue_to_merged_pr_files(self) -> None:
        issues = [{
            "number": 12,
            "title": "Scanner misses a career page",
            "state": "closed",
            "closed_at": "2026-10-01T10:00:00Z",
            "labels": [{"name": "bug"}, {"name": "high"}],
        }]
        pull_requests = [{
            "number": 24,
            "title": "Handle empty career page response",
            "body": "Fixes #12",
            "merged_at": "2026-10-02T10:00:00Z",
        }]
        changed_files = [
            {"filename": "v2/flows/careers/scanner.py"},
            {"filename": "v2/tests/test_career_scanner.py"},
            {"filename": "v1/src/scanner.py"},
        ]
        environment = {
            "GITHUB_TOKEN": "test-token",
            "GITHUB_REPOSITORY": "mbraga2023/Job-bot",
        }

        with (
            patch.object(insights, "get_env", side_effect=lambda name, default=None: environment.get(name, default)),
            patch.object(
                insights,
                "_github_paginated_list",
                side_effect=[issues, pull_requests, changed_files],
            ) as paginate,
        ):
            data = insights.get_github_defect_history()

        self.assertEqual(data["status"], "available")
        self.assertEqual(data["mapped_defects"], 1)
        self.assertEqual(
            data["files"]["v2/flows/careers/scanner.py"],
            {"defect_count": 1, "severity_weighted_defects": 3},
        )
        self.assertEqual(paginate.call_count, 3)

    def test_github_defect_history_reports_missing_token_without_network_call(self) -> None:
        with (
            patch.object(insights, "get_env", return_value=None),
            patch.object(insights, "_github_api_get") as api_get,
        ):
            data = insights.get_github_defect_history()

        self.assertEqual(data["status"], "unavailable")
        self.assertIn("GITHUB_TOKEN", data["reason"])
        api_get.assert_not_called()

    def test_github_pagination_preserves_existing_query_parameters(self) -> None:
        with patch.object(insights, "_github_api_get", return_value=[]) as api_get:
            data = insights._github_paginated_list(
                "mbraga2023/Job-bot",
                "issues?state=all",
                "test-token",
            )

        self.assertEqual(data, [])
        self.assertEqual(
            api_get.call_args.args[1],
            "issues?state=all&per_page=100&page=1",
        )

    def test_github_api_uses_token_only_in_authorization_header(self) -> None:
        token = "local-test-token"
        with patch.object(insights, "urlopen", return_value=BytesIO(b'{"ok": true}')) as open_url:
            data = insights._github_api_get("mbraga2023/Job-bot", "issues", token)

        request = open_url.call_args.args[0]
        self.assertEqual(data, {"ok": True})
        self.assertEqual(request.get_header("Authorization"), f"Bearer {token}")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertNotIn(token, json.dumps(data))

    def test_ollama_analysis_uses_local_measured_evidence_and_validates_module_ids(self) -> None:
        scenario_coverage = {
            "coverage_percent": 75.0,
            "measured_modules": 1,
            "modules": [{
                "id": "careers",
                "name": "Fluxo de carreiras",
                "scenario_coverage_percent": 75.0,
                "covered_scenarios": 3,
                "total_scenarios": 4,
                "risk_weight_percent": 60.0,
                "recent_commits": 4,
                "severity_weighted_defects": None,
                "scenarios": [{"name": "Validação de fonte", "status": "uncovered"}],
            }],
            "missing_risk_inputs": ["mapped GitHub defect history"],
        }
        response = SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "priority_module_ids": ["careers"],
        })))
        with patch("ollama.Client") as client_class:
            client_class.return_value.chat.return_value = response
            result = insights.analyze_test_risk_with_ollama(
                scenario_coverage,
                [{"id": "careers", "coverage_percent": 42.0, "branch_coverage_percent": 35.0}],
                {"status": "no_labeled_defects"},
            )

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["kind"], "qualitative_local_llm_review")
        self.assertEqual(result["priorities"][0]["module_name"], "Fluxo de carreiras")
        call = client_class.return_value.chat.call_args.kwargs
        self.assertEqual(call["model"], insights.config.ollama_model)
        prompt = " ".join(message["content"] for message in call["messages"])
        self.assertIn("probabilities", prompt)
        self.assertIn("scenario_gaps", prompt)
        self.assertNotIn("source code", prompt)

    def test_ollama_analysis_reports_unavailable_when_service_fails(self) -> None:
        import ollama

        scenario_coverage = {
            "coverage_percent": 50.0,
            "measured_modules": 1,
            "modules": [{
                "id": "careers",
                "name": "Fluxo de carreiras",
                "scenario_coverage_percent": 50.0,
                "covered_scenarios": 1,
                "total_scenarios": 2,
                "risk_weight_percent": 100.0,
                "recent_commits": 1,
                "severity_weighted_defects": None,
                "scenarios": [{"name": "Teste de navegação", "status": "uncovered"}],
            }],
            "missing_risk_inputs": ["mapped GitHub defect history"],
        }
        with patch("ollama.Client", side_effect=ollama.RequestError("connection refused")):
            result = insights.analyze_test_risk_with_ollama(
                scenario_coverage,
                [],
                {"status": "no_labeled_defects"},
            )

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("connection refused", result["reason"])
        self.assertEqual(result["priorities"], [])

    def test_coverage_analysis_runs_qualitative_ai_analysis_without_claiming_prediction(self) -> None:
        coverage_data = {
            "tests_run": 114,
            "test_outcomes": self.passing_scenario_outcomes(),
            "flows": [{
                "id": "careers",
                "files": [
                    {"path": "v2/flows/careers/a.py", "covered_lines": 50, "total_lines": 100},
                ],
            }],
        }
        repository_data = {
            "modules": [{"id": "careers", "file_commits": {"v2/flows/careers/a.py": 2}}],
        }
        with (
            patch.object(insights, "get_test_coverage", return_value=coverage_data),
            patch.object(insights, "get_repository_test_insights", return_value=repository_data) as get_insights,
            patch.object(
                insights,
                "get_github_defect_history",
                return_value={"status": "unavailable", "files": {}, "reason": "No token"},
            ),
            patch.object(
                insights,
                "analyze_test_risk_with_ollama",
                return_value={
                    "status": "available",
                    "kind": "qualitative_local_llm_review",
                    "summary": "Prioritize untested scenarios.",
                    "priorities": [],
                },
            ) as analyze_ai,
        ):
            data = insights.get_coverage_analysis(7)

        self.assertEqual(
            data["risk_weighted_scenario_coverage"]["status"],
            "available",
        )
        self.assertIn(
            "mapped GitHub defect history",
            data["risk_weighted_scenario_coverage"]["missing_risk_inputs"],
        )
        self.assertEqual(data["ai_risk_analysis"]["status"], "available")
        self.assertEqual(data["ai_risk_analysis"]["kind"], "qualitative_local_llm_review")
        analyze_ai.assert_called_once()
        self.assertEqual(data["analysis_period_days"], 7)
        self.assertNotIn("test_outcomes", data)
        get_insights.assert_called_once_with(7)

    def test_coverage_analysis_rejects_invalid_period_before_running_tests(self) -> None:
        with patch.object(insights, "get_test_coverage") as run_coverage:
            with self.assertRaisesRegex(ValueError, "7, 30, or 90"):
                insights.get_coverage_analysis(14)

        run_coverage.assert_not_called()

    def test_git_failure_keeps_measured_coverage_and_marks_weighting_unavailable(self) -> None:
        coverage_data = {"coverage_percent": 50.0, "flows": []}
        with (
            patch.object(insights, "get_test_coverage", return_value=coverage_data),
            patch.object(
                insights,
                "get_repository_test_insights",
                side_effect=subprocess.CalledProcessError(128, ["git"], stderr="git unavailable"),
            ),
            patch.object(
                insights,
                "get_github_defect_history",
                return_value={"status": "unavailable", "files": {}, "reason": "No token"},
            ),
        ):
            data = insights.get_coverage_analysis()

        self.assertEqual(data["coverage_percent"], 50.0)
        self.assertEqual(data["risk_weighted_scenario_coverage"]["status"], "unavailable")
        self.assertIn("git unavailable", data["risk_weighted_scenario_coverage"]["reason"])

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
        self.assertEqual(core["file_commits"], {"v2/core/database.py": 1})
        self.assertEqual(core["test_files"], ["test_database.py"])
        self.assertEqual(dashboard["commits"], 1)
        self.assertEqual(dashboard["file_commits"], {"v2/dashboard/server.py": 1})
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
