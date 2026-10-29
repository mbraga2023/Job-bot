"""Repository-backed test prioritization insights from Git history."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DIRECTORY = PROJECT_ROOT / "v2" / "tests"
MODULES = (
    {
        "id": "core",
        "name": "Core e configuração",
        "path": "v2/core/",
        "tests": (
            "test_config.py",
            "test_database.py",
            "test_date_utils.py",
            "test_keywords.py",
            "test_qa_classifier.py",
            "test_seniority.py",
        ),
    },
    {
        "id": "careers",
        "name": "Fluxo de carreiras",
        "path": "v2/flows/careers/",
        "tests": (
            "test_career_adapters.py",
            "test_career_scanner.py",
            "test_career_validator.py",
            "test_migration.py",
        ),
    },
    {
        "id": "telegram",
        "name": "Telegram e LinkedIn",
        "path": "v2/flows/telegram/",
        "tests": (
            "test_telegram_collector.py",
            "test_telegram_validator.py",
            "test_linkedin_analyzer.py",
            "test_linkedin_validation.py",
            "test_reviewers.py",
        ),
    },
    {
        "id": "dashboard",
        "name": "Dashboard",
        "path": "v2/dashboard/",
        "tests": ("test_dashboard.py",),
    },
    {
        "id": "cli",
        "name": "CLI",
        "path": "v2/main.py",
        "tests": (),
    },
)
COMMIT_HEADER = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})\t(?P<hash>[0-9a-f]+)")
COVERAGE_RUNNER = r"""
import ast
import io
import json
import threading
import trace
import unittest
from datetime import datetime
from pathlib import Path
import sys

root = Path.cwd().resolve()
source_root = root / "v2"
test_root = source_root / "tests"
executable_lines = set()
docstring_expressions = set()

def collect_docstrings(node):
    body = getattr(node, "body", ())
    if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        docstring_expressions.add(id(body[0]))
    for child in ast.iter_child_nodes(node):
        collect_docstrings(child)

def collect_statements(node):
    for child in ast.walk(node):
        if not isinstance(child, ast.stmt):
            continue
        if id(child) in docstring_expressions:
            continue
        executable_lines.add((str(source_file.resolve()), child.lineno))

for source_file in source_root.rglob("*.py"):
    if "tests" in source_file.relative_to(source_root).parts or "__pycache__" in source_file.parts:
        continue
    try:
        parsed = ast.parse(source_file.read_text(encoding="utf-8"))
        collect_docstrings(parsed)
        collect_statements(parsed)
    except (OSError, SyntaxError) as error:
        raise RuntimeError(f"Could not inspect {source_file}: {error}") from error

suite = unittest.defaultTestLoader.discover(str(test_root), top_level_dir=str(root))
runner = unittest.TextTestRunner(stream=io.StringIO())
tracer = trace.Trace(count=True, trace=False, ignoredirs=[sys.prefix, sys.base_prefix])
threading.settrace(tracer.globaltrace)
result = tracer.runfunc(runner.run, suite)
counts = tracer.results().counts
executed_lines = {
    (str(Path(filename).resolve()), line)
    for (filename, line), count in counts.items()
    if count > 0
}
covered = len(executable_lines & executed_lines)
total = len(executable_lines)
test_issues = [
    {
        "test": test.id(),
        "kind": kind,
        "detail": detail.strip().splitlines()[-1] if detail.strip() else "",
    }
    for kind, tests in (("failure", result.failures), ("error", result.errors))
    for test, detail in tests
]
print(json.dumps({
    "coverage_percent": round(covered / total * 100, 1) if total else 0,
    "covered_lines": covered,
    "total_lines": total,
    "tests_run": result.testsRun,
    "test_failures": len(result.failures),
    "test_errors": len(result.errors),
    "test_issues": test_issues,
    "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
}))
"""


def _parse_git_log(output: str) -> list[dict[str, Any]]:
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for token in output.split("\0"):
        value = token.strip("\r\n")
        header = COMMIT_HEADER.fullmatch(value)
        if header:
            current = {"date": header.group("date"), "files": set()}
            commits.append(current)
        elif current is not None and value.startswith("v2/"):
            current["files"].add(value)
    return commits


def get_repository_test_insights(days: int) -> dict[str, Any]:
    """Return real code-change activity and existing test-file associations."""
    if days not in (7, 30, 90):
        raise ValueError("Period must be 7, 30, or 90 days.")

    since = date.today() - timedelta(days=days - 1)
    result = subprocess.run(
        [
            "git",
            "log",
            f"--since={since.isoformat()} 00:00",
            "--format=%cs%x09%H",
            "--name-only",
            "-z",
            "--",
            "v2",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=True,
    )
    commits = _parse_git_log(result.stdout)
    existing_tests = {path.name for path in TEST_DIRECTORY.glob("test_*.py")}
    dates = [
        (since + timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]
    source_commits = [
        commit
        for commit in commits
        if any(
            path.startswith("v2/")
            and not path.startswith("v2/tests/")
            and path.endswith(".py")
            for path in commit["files"]
        )
    ]
    source_files = {
        path
        for commit in source_commits
        for path in commit["files"]
        if path.startswith("v2/")
        and not path.startswith("v2/tests/")
        and path.endswith(".py")
    }

    module_data = []
    for module in MODULES:
        relevant = [
            commit
            for commit in commits
            if any(
                path.startswith(module["path"]) and path.endswith(".py")
                for path in commit["files"]
            )
        ]
        files_changed = sorted({
            path
            for commit in relevant
            for path in commit["files"]
            if path.startswith(module["path"]) and path.endswith(".py")
        })
        associated_tests = [
            name for name in module["tests"] if name in existing_tests
        ]
        trend = [
            sum(commit["date"] == day for commit in relevant)
            for day in dates
        ]
        module_data.append({
            "id": module["id"],
            "name": module["name"],
            "path": module["path"],
            "commits": len(relevant),
            "files_changed": len(files_changed),
            "test_files": associated_tests,
            "test_file_count": len(associated_tests),
            "trend": trend,
        })

    return {
        "days": days,
        "since": since.isoformat(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "summary": {
            "commits": len(source_commits),
            "files_changed": len(source_files),
        },
        "modules": module_data,
        "trend": [
            {
                "date": day,
                "commits": sum(
                    commit["date"] == day for commit in source_commits
                ),
            }
            for day in dates
        ],
    }


def get_test_coverage() -> dict[str, Any]:
    """Run the v2 unit suite under the stdlib tracer and report source-line coverage."""
    result = subprocess.run(
        [sys.executable, "-c", COVERAGE_RUNNER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=True,
    )
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError("The test coverage run returned invalid output.") from exc
