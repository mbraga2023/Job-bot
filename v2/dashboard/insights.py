"""Repository-backed test prioritization insights from Git history."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from v2.config import get_env

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
SCENARIO_CATALOG = {
    "core": (
        {
            "id": "optional-configuration",
            "name": "Configuração funciona sem credenciais opcionais",
            "test_cases": ("test_config.py::test_app_config_does_not_require_telegram_env",),
        },
        {
            "id": "job-persistence-lifecycle",
            "name": "Persistência e ciclo de vida de vagas",
            "test_cases": (
                "test_database.py::test_schema_creation",
                "test_database.py::test_telegram_and_career_jobs_lifecycle",
            ),
        },
        {
            "id": "qa-classification",
            "name": "Classificação de vagas QA e evidências de tecnologia",
            "test_cases": (
                "test_keywords.py::test_qa_title_filter_rejects_non_qa_and_promotional_titles",
                "test_keywords.py::test_reported_portuguese_qa_titles_are_recognized",
                "test_keywords.py::test_qa_technology_evidence",
            ),
        },
        {
            "id": "date-normalization",
            "name": "Normalização de datas",
            "test_cases": (
                "test_date_utils.py::test_normalize_iso_date",
                "test_date_utils.py::test_normalize_portuguese_date",
            ),
        },
        {
            "id": "seniority-filtering",
            "name": "Priorização por senioridade",
            "test_cases": (
                "test_seniority.py::test_eligible_mid_level",
                "test_seniority.py::test_discard_junior_and_intern",
                "test_seniority.py::test_discard_senior_and_lead",
            ),
        },
        {
            "id": "invalid-llm-response",
            "name": "Tratamento de resposta inválida do modelo",
            "test_cases": (
                "test_qa_classifier.py::test_malformed_json_final_review_raises_clear_error",
                "test_qa_classifier.py::test_invalid_final_review_response_raises",
            ),
        },
    ),
    "careers": (
        {
            "id": "validated-job-details",
            "name": "Adaptadores exigem detalhes e título QA válidos",
            "test_cases": (
                "test_career_adapters.py::test_requires_job_detail_url_and_qa_title_before_returning_job",
                "test_career_adapters.py::test_only_qa_job_cards_are_returned",
            ),
        },
        {
            "id": "source-search-filtering",
            "name": "Busca e filtros por fonte",
            "test_cases": (
                "test_career_adapters.py::test_search_fills_gupy_field_and_presses_enter",
                "test_career_scanner.py::test_gupy_only_filters_sources_and_searches_each_term",
            ),
        },
        {
            "id": "navigation-recovery",
            "name": "Recuperação de navegação e redirecionamentos",
            "test_cases": (
                "test_career_scanner.py::test_navigation_retries_transient_dns_failures",
                "test_career_scanner.py::test_navigation_waits_for_redirect_when_superseded",
            ),
        },
        {
            "id": "candidate-freshness",
            "name": "Regras de elegibilidade por origem e data",
            "test_cases": (
                "test_career_scanner.py::test_recent_sources_are_skipped_and_search_all_includes_inhire",
                "test_career_scanner.py::test_future_or_invalid_check_timestamp_is_not_eligible",
            ),
        },
        {
            "id": "candidate-insertion-gates",
            "name": "Vagas inválidas não são inseridas",
            "test_cases": (
                "test_career_scanner.py::test_scanner_does_not_insert_non_qa_or_untitled_items",
                "test_career_validator.py::test_rejects_unrelated_titles_without_calling_ollama",
            ),
        },
        {
            "id": "work-model-validation",
            "name": "Validação de trabalho remoto e híbrido",
            "test_cases": (
                "test_career_validator.py::test_gupy_work_model_only_passes_explicit_remote_values",
                "test_career_validator.py::test_gupy_title_detects_hybrid_and_other_non_remote_markers",
                "test_career_validator.py::test_gupy_hybrid_job_is_discarded_before_llm",
            ),
        },
    ),
    "telegram": (
        {
            "id": "collection-and-classification",
            "name": "Coleta e classificação de vagas",
            "test_cases": (
                "test_telegram_collector.py::test_collects_non_qa_title_without_filtering",
                "test_telegram_validator.py::test_non_qa_title_is_rejected_without_llm",
            ),
        },
        {
            "id": "remote-work-gate",
            "name": "Filtro de trabalho remoto",
            "test_cases": (
                "test_telegram_validator.py::test_non_remote_job_is_rejected_without_llm",
                "test_telegram_validator.py::test_hybrid_and_onsite_are_not_remote",
                "test_telegram_validator.py::test_mixed_remote_and_hybrid_is_not_remote",
            ),
        },
        {
            "id": "candidate-quality-gates",
            "name": "Gates de senioridade e evidência técnica",
            "test_cases": (
                "test_telegram_validator.py::test_seniority_is_rejected_without_llm",
                "test_telegram_validator.py::test_llm_final_review_runs_only_after_all_three_gates",
                "test_telegram_validator.py::test_technology_evidence_is_cross_checked_by_final_llm",
            ),
        },
        {
            "id": "final-review-rejection",
            "name": "Rejeição na revisão final",
            "test_cases": (
                "test_telegram_validator.py::test_llm_final_rejection_discards_job",
            ),
        },
        {
            "id": "retry-and-login-handling",
            "name": "Tratamento de login e falhas recuperáveis",
            "test_cases": (
                "test_telegram_validator.py::test_login_required_warns_and_leaves_job_pending",
                "test_telegram_validator.py::test_ollama_failure_leaves_job_pending_for_retry",
            ),
        },
        {
            "id": "linkedin-application-flow",
            "name": "Fluxo de candidatura do LinkedIn",
            "test_cases": (
                "test_linkedin_validation.py::test_easy_apply_sets_status_without_fetching_application_url",
                "test_linkedin_validation.py::test_non_easy_apply_updates_application_url_from_apply_link",
                "test_linkedin_analyzer.py::test_application_url_returns_linkedin_safety_destination_unchanged",
            ),
        },
        {
            "id": "review-batch-limits",
            "name": "Limite e status dos lotes de revisão",
            "test_cases": (
                "test_reviewers.py::test_telegram_review_caps_batch_at_ten",
                "test_reviewers.py::test_career_review_caps_batch_at_ten",
            ),
        },
    ),
    "dashboard": (
        {
            "id": "live-insights-page",
            "name": "Página de insights usa dados reais",
            "test_cases": ("test_dashboard.py::test_test_insights_page_uses_real_repository_data",),
        },
        {
            "id": "coverage-reporting",
            "name": "Relatório de cobertura da suíte",
            "test_cases": (
                "test_dashboard_insights.py::test_test_coverage_parses_line_and_branch_report",
                "test_dashboard.py::test_test_coverage_endpoint_returns_measured_suite_results",
            ),
        },
        {
            "id": "github-defect-mapping",
            "name": "Mapeamento seguro de issues e arquivos por PR",
            "test_cases": (
                "test_dashboard_insights.py::test_github_defect_history_maps_bug_issue_to_merged_pr_files",
                "test_dashboard_insights.py::test_github_api_uses_token_only_in_authorization_header",
            ),
        },
        {
            "id": "unavailable-external-data",
            "name": "Comportamento explícito sem token ou sem Git",
            "test_cases": (
                "test_dashboard_insights.py::test_github_defect_history_reports_missing_token_without_network_call",
                "test_dashboard_insights.py::test_git_failure_keeps_measured_coverage_and_marks_weighting_unavailable",
            ),
        },
        {
            "id": "invalid-analysis-period",
            "name": "Validação de períodos de análise",
            "test_cases": (
                "test_dashboard_insights.py::test_coverage_analysis_rejects_invalid_period_before_running_tests",
                "test_dashboard.py::test_repository_insights_endpoint_reports_invalid_period",
            ),
        },
    ),
}
COMMIT_HEADER = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})\t(?P<hash>[0-9a-f]+)")
GITHUB_REPOSITORY = "mbraga2023/Job-bot"
GITHUB_API_URL = "https://api.github.com"
GITHUB_PAGE_SIZE = 100
GITHUB_MAX_PAGES = 20
GITHUB_CLOSING_REFERENCE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+"
    r"(?:(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+))?#(?P<number>\d+)",
    re.IGNORECASE,
)
COVERAGE_RUNNER = r"""
import json
import unittest
from datetime import datetime
from pathlib import Path
import tempfile
import sys

class TrackingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.setdefault(test.id(), "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "failed"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "failed"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes[test.id()] = "failed"
        else:
            self.outcomes.setdefault(test.id(), "passed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "skipped"

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcomes[test.id()] = "failed"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcomes[test.id()] = "failed"

root = Path.cwd().resolve()
source_root = root / "v2"
test_root = source_root / "tests"
import coverage

suite = unittest.defaultTestLoader.discover(str(test_root), top_level_dir=str(root))
runner = unittest.TextTestRunner(stream=sys.stderr, resultclass=TrackingResult)
measurement = coverage.Coverage(
    source=[
        str(source_root),
        str(source_root / "flows" / "careers"),
        str(source_root / "flows" / "telegram"),
    ],
    branch=True,
    omit=["*/tests/*", "*/__pycache__/*"],
    data_file=None,
)
measurement.start()
result = runner.run(suite)
measurement.stop()
with tempfile.TemporaryDirectory() as temporary_directory:
    report_path = Path(temporary_directory) / "coverage.json"
    measurement.json_report(outfile=str(report_path))
    report = json.loads(report_path.read_text(encoding="utf-8"))

totals = report["totals"]
total = totals["num_statements"]
covered = totals["covered_lines"]
branch_total = totals["num_branches"]
covered_branches = totals["covered_branches"]
flow_coverage = []
for flow_id, flow_name in (
    ("careers", "Fluxo de carreiras"),
    ("telegram", "Telegram e LinkedIn"),
):
    flow_prefix = f"flows/{flow_id}/"
    files = []
    flow_covered = 0
    flow_total = 0
    flow_branches = 0
    flow_branch_total = 0
    for filename, file_report in report["files"].items():
        relative_path = Path(filename).resolve().relative_to(source_root).as_posix()
        if not relative_path.startswith(flow_prefix):
            continue
        summary = file_report["summary"]
        covered_file_lines = summary["covered_lines"]
        total_file_lines = summary["num_statements"]
        file_branches = summary["covered_branches"]
        file_branch_total = summary["num_branches"]
        flow_covered += covered_file_lines
        flow_total += total_file_lines
        flow_branches += file_branches
        flow_branch_total += file_branch_total
        files.append({
            "path": (Path("v2") / relative_path).as_posix(),
            "covered_lines": covered_file_lines,
            "total_lines": total_file_lines,
            "coverage_percent": round(covered_file_lines / total_file_lines * 100, 1)
            if total_file_lines else 0,
            "covered_branches": file_branches,
            "total_branches": file_branch_total,
            "branch_coverage_percent": round(file_branches / file_branch_total * 100, 1)
            if file_branch_total else None,
        })
    flow_coverage.append({
        "id": flow_id,
        "name": flow_name,
        "covered_lines": flow_covered,
        "total_lines": flow_total,
        "coverage_percent": round(flow_covered / flow_total * 100, 1)
        if flow_total else 0,
        "covered_branches": flow_branches,
        "total_branches": flow_branch_total,
        "branch_coverage_percent": round(flow_branches / flow_branch_total * 100, 1)
        if flow_branch_total else None,
        "files": sorted(files, key=lambda item: item["path"]),
    })
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
    "line_coverage_percent": round(covered / total * 100, 1) if total else 0,
    "covered_lines": covered,
    "total_lines": total,
    "branch_coverage_percent": round(covered_branches / branch_total * 100, 1)
    if branch_total else None,
    "covered_branches": covered_branches,
    "total_branches": branch_total,
    "flows": flow_coverage,
    "coverage_tool": "coverage.py",
    "coverage_tool_version": coverage.__version__,
    "tests_run": result.testsRun,
    "test_failures": len(result.failures),
    "test_errors": len(result.errors),
    "test_issues": test_issues,
    "test_outcomes": result.outcomes,
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
        file_commits = {
            path: sum(path in commit["files"] for commit in relevant)
            for path in files_changed
        }
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
            "file_commits": file_commits,
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
    """Run the v2 suite with coverage.py and report line and branch coverage."""
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


def _github_repository_and_token() -> tuple[str | None, str | None, str | None]:
    token = get_env("GITHUB_TOKEN")
    repository = get_env("GITHUB_REPOSITORY", default=GITHUB_REPOSITORY)
    token = token.strip() if token else None
    repository = repository.strip() if repository else None
    if not token:
        return repository, None, "Defina GITHUB_TOKEN localmente para consultar issues."
    if not repository or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        repository,
    ):
        return None, token, "GITHUB_REPOSITORY deve estar no formato owner/repository."
    return repository, token, None


def _github_api_get(repository: str, endpoint: str, token: str) -> Any:
    url = f"{GITHUB_API_URL}/repos/{quote(repository, safe='/')}/{endpoint}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Job-bot-Test-Insights",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"A API do GitHub retornou HTTP {exc.code} para {endpoint}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Não foi possível conectar à API do GitHub: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"A API do GitHub retornou JSON inválido para {endpoint}.") from exc


def _github_paginated_list(
    repository: str,
    endpoint: str,
    token: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in range(1, GITHUB_MAX_PAGES + 1):
        separator = "&" if "?" in endpoint else "?"
        response = _github_api_get(
            repository,
            f"{endpoint}{separator}per_page={GITHUB_PAGE_SIZE}&page={page}",
            token,
        )
        if not isinstance(response, list):
            raise RuntimeError(f"A API do GitHub retornou uma lista inválida para {endpoint}.")
        items.extend(item for item in response if isinstance(item, dict))
        if len(response) < GITHUB_PAGE_SIZE:
            return items
    raise RuntimeError(
        f"GitHub {endpoint} excede o limite de {GITHUB_MAX_PAGES * GITHUB_PAGE_SIZE} registros."
    )


def _is_labeled_defect(
    issue: dict[str, Any],
    defect_labels: set[str],
) -> bool:
    issue_labels = issue.get("labels")
    if not isinstance(issue_labels, list):
        issue_labels = []
    labels = {
        str(label.get("name", "")).casefold()
        for label in issue_labels
        if isinstance(label, dict)
    }
    issue_type = issue.get("type")
    if isinstance(issue_type, dict):
        labels.add(str(issue_type.get("name", "")).casefold())
    return bool(labels & defect_labels)


def _severity_weight(issue: dict[str, Any]) -> int:
    issue_labels = issue.get("labels")
    if not isinstance(issue_labels, list):
        issue_labels = []
    labels = [
        str(label.get("name", "")).casefold()
        for label in issue_labels
        if isinstance(label, dict)
    ]
    for label in labels:
        if any(value in label for value in ("critical", "sev1", "p0")):
            return 5
    for label in labels:
        if any(value in label for value in ("high", "sev2", "p1")):
            return 3
    for label in labels:
        if any(value in label for value in ("medium", "sev3", "p2")):
            return 2
    return 1


def _closing_issue_numbers(
    text: str,
    repository: str,
) -> set[int]:
    issue_numbers: set[int] = set()
    for match in GITHUB_CLOSING_REFERENCE.finditer(text):
        referenced_repository = match.group("repository")
        if referenced_repository and referenced_repository.casefold() != repository.casefold():
            continue
        issue_numbers.add(int(match.group("number")))
    return issue_numbers


def get_github_defect_history() -> dict[str, Any]:
    """Map bug-labeled GitHub issues to files changed in their merged closing PRs."""
    repository, token, configuration_error = _github_repository_and_token()
    if configuration_error or not repository or not token:
        return {
            "status": "unavailable",
            "repository": repository,
            "reason": configuration_error or "GitHub issue access is not configured.",
            "issues_scanned": 0,
            "labeled_defects": 0,
            "mapped_defects": 0,
            "unmapped_defects": 0,
            "open_defects": 0,
            "files": {},
        }

    defect_labels = {
        label.strip().casefold()
        for label in get_env(
            "GITHUB_DEFECT_LABELS",
            default="bug,defect,defeito",
        ).split(",")
        if label.strip()
    }
    try:
        issue_records = _github_paginated_list(
            repository,
            "issues?state=all",
            token,
        )
        defects = [
            issue for issue in issue_records
            if "pull_request" not in issue
            and isinstance(issue.get("number"), int)
            and _is_labeled_defect(issue, defect_labels)
        ]
        closed_defects = {
            issue["number"]: issue
            for issue in defects
            if issue.get("state") == "closed" and issue.get("closed_at")
        }
        open_defects = sum(issue.get("state") == "open" for issue in defects)
        pull_requests = _github_paginated_list(
            repository,
            "pulls?state=closed",
            token,
        )
        linked_files: dict[int, set[str]] = {}
        closed_prs = [
            pull_request
            for pull_request in pull_requests
            if pull_request.get("merged_at")
        ]
        for pull_request in closed_prs:
            pull_request_number = pull_request.get("number")
            if not isinstance(pull_request_number, int):
                continue
            title = pull_request.get("title") or ""
            body = pull_request.get("body") or ""
            issue_numbers = _closing_issue_numbers(
                f"{title}\n{body}",
                repository,
            ) & closed_defects.keys()
            if not issue_numbers:
                continue
            changed_files = _github_paginated_list(
                repository,
                f"pulls/{pull_request_number}/files",
                token,
            )
            source_paths: set[str] = set()
            for item in changed_files:
                filename = item.get("filename")
                if not isinstance(filename, str):
                    continue
                relative_path = PurePosixPath(filename)
                if (
                    not relative_path.is_absolute()
                    and ".." not in relative_path.parts
                    and relative_path.parts[0:1] == ("v2",)
                    and relative_path.suffix == ".py"
                    and PROJECT_ROOT.joinpath(*relative_path.parts).is_file()
                ):
                    source_paths.add(relative_path.as_posix())
            for issue_number in issue_numbers:
                linked_files.setdefault(issue_number, set()).update(source_paths)

        files: dict[str, dict[str, int]] = {}
        for issue_number, paths in linked_files.items():
            issue = closed_defects[issue_number]
            weight = _severity_weight(issue)
            for path in paths:
                file = files.setdefault(
                    path,
                    {"defect_count": 0, "severity_weighted_defects": 0},
                )
                file["defect_count"] += 1
                file["severity_weighted_defects"] += weight
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        return {
            "status": "unavailable",
            "repository": repository,
            "reason": f"Não foi possível consultar o histórico de defeitos no GitHub: {exc}",
            "issues_scanned": 0,
            "labeled_defects": 0,
            "mapped_defects": 0,
            "unmapped_defects": 0,
            "open_defects": 0,
            "files": {},
        }

    mapped_issue_numbers = set(linked_files)
    labeled_defect_count = len(defects)
    mapped_defect_count = len(mapped_issue_numbers)
    if mapped_defect_count:
        status = "available"
        reason = None
    elif labeled_defect_count:
        status = "no_mapped_defects"
        reason = (
            "Há issues identificadas como defeitos, mas nenhuma foi associada "
            "com segurança a arquivos por um PR merged com referência de fechamento."
        )
    else:
        status = "no_labeled_defects"
        reason = (
            "Nenhuma issue com os labels/tipos configurados para defeitos foi encontrada; "
            "isso não significa que não houve defeitos."
        )
    return {
        "status": status,
        "repository": repository,
        "reason": reason,
        "issues_scanned": len(issue_records),
        "labeled_defects": labeled_defect_count,
        "mapped_defects": mapped_defect_count,
        "unmapped_defects": max(0, len(closed_defects) - mapped_defect_count),
        "open_defects": open_defects,
        "files": files,
        "mapping": "closed bug-labeled issue -> merged PR closing reference -> changed v2 Python files",
        "retrieved_at": datetime.now().astimezone().isoformat(timespec="minutes"),
    }


def annotate_file_attention(
    flows: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    defect_history: dict[str, Any] | None = None,
) -> None:
    """Add relative file attention scores without conflating them with coverage."""
    defect_history = defect_history or {}
    defect_files = defect_history.get("files", {})
    activity_by_flow = {
        module["id"]: module.get("file_commits", {})
        for module in modules
    }
    risk_points_by_file: list[tuple[dict[str, Any], float]] = []

    for flow in flows:
        file_commits = activity_by_flow.get(flow["id"], {})
        for file in flow["files"]:
            total_lines = file.get("total_lines", 0)
            if total_lines <= 0:
                continue
            commits = max(0, file_commits.get(file["path"], 0))
            historical = defect_files.get(file["path"], {})
            defect_count = historical.get("defect_count", 0)
            severity_weighted_defects = historical.get("severity_weighted_defects", 0)
            risk_weight = 1 + commits + severity_weighted_defects
            line_coverage = file["covered_lines"] / total_lines
            file["recent_commits"] = commits
            file["historical_defects"] = defect_count
            file["risk_weight"] = risk_weight
            risk_points_by_file.append((file, risk_weight * (1 - line_coverage)))

    max_risk_points = max((points for _, points in risk_points_by_file), default=0.0)
    for file, points in risk_points_by_file:
        file["heuristic_risk_score"] = (
            round(points / max_risk_points * 100, 1) if max_risk_points else None
        )


def _test_case_outcomes(
    test_case: str,
    outcomes: dict[str, str],
) -> list[str]:
    filename, separator, method_name = test_case.partition("::")
    if not separator:
        raise ValueError(f"Invalid scenario test reference: {test_case}")
    module_name = Path(filename).stem
    module_marker = f".{module_name}."
    method_marker = f".{method_name}"
    return [
        outcome
        for test_id, outcome in outcomes.items()
        if module_marker in test_id and test_id.endswith(method_marker)
    ]


def _weighted_scenario_percentage(modules: list[dict[str, Any]]) -> float | None:
    total_weight = sum(module["risk_weight_raw"] for module in modules)
    if not total_weight:
        return None
    weighted_total = sum(
        module["risk_weight_raw"] * module["scenario_coverage"]
        for module in modules
    )
    return weighted_total / total_weight * 100


def calculate_risk_weighted_scenario_coverage(
    test_outcomes: dict[str, str],
    modules: list[dict[str, Any]],
    defect_history: dict[str, Any] | None = None,
    *,
    tests_run: int,
    git_data_available: bool,
) -> dict[str, Any]:
    """Weight curated, passing test scenarios by normalized module risk."""
    defect_history = defect_history or {}
    defect_files = defect_history.get("files", {})
    github_status = defect_history.get("status")
    github_data_available = github_status == "available"
    activity_by_module = {module["id"]: module for module in modules}
    measured_modules: list[dict[str, Any]] = []
    unmeasured_modules: list[dict[str, Any]] = []

    for module_definition in MODULES:
        scenarios = SCENARIO_CATALOG.get(module_definition["id"], ())
        if not scenarios:
            continue
        module_activity = activity_by_module.get(module_definition["id"], {})
        recent_commits: int | None = (
            max(0, module_activity.get("commits", 0)) if git_data_available else None
        )
        severity_weighted_defects = (
            sum(
                item.get("severity_weighted_defects", 0)
                for path, item in defect_files.items()
                if path.startswith(module_definition["path"])
            )
            if github_data_available else None
        )
        scenario_results: list[dict[str, Any]] = []
        covered_scenarios = 0
        observed_scenarios = 0
        for scenario in scenarios:
            case_outcomes = [
                _test_case_outcomes(test_case, test_outcomes)
                for test_case in scenario["test_cases"]
            ]
            has_observation = any(case_outcomes)
            if has_observation:
                observed_scenarios += 1
            scenario_covered = bool(case_outcomes) and all(
                outcomes and all(outcome == "passed" for outcome in outcomes)
                for outcomes in case_outcomes
            )
            if scenario_covered:
                covered_scenarios += 1
            scenario_results.append({
                "id": scenario["id"],
                "name": scenario["name"],
                "status": (
                    "covered" if scenario_covered
                    else "uncovered" if has_observation or tests_run > 0
                    else "unknown"
                ),
                "test_cases": list(scenario["test_cases"]),
            })

        scenario_coverage = (
            covered_scenarios / len(scenarios)
            if tests_run > 0 else None
        )
        raw_risk_weight = (
            1
            + (recent_commits or 0)
            + (severity_weighted_defects or 0)
        )
        module_result = {
            "id": module_definition["id"],
            "name": module_definition["name"],
            "scenario_coverage": scenario_coverage,
            "scenario_coverage_percent": (
                round(scenario_coverage * 100, 1)
                if scenario_coverage is not None else None
            ),
            "covered_scenarios": covered_scenarios if tests_run > 0 else None,
            "total_scenarios": len(scenarios),
            "observed_scenarios": observed_scenarios if tests_run > 0 else None,
            "risk_weight_raw": raw_risk_weight,
            "risk_weight": None,
            "risk_weight_percent": None,
            "recent_commits": recent_commits,
            "severity_weighted_defects": severity_weighted_defects,
            "scenarios": scenario_results,
        }
        if scenario_coverage is None:
            unmeasured_modules.append({
                **module_result,
                "reason": "A suíte não executou testes para medir cenários.",
            })
        else:
            measured_modules.append(module_result)

    risk_sources_available = git_data_available or github_data_available
    total_raw_weight = sum(module["risk_weight_raw"] for module in measured_modules)
    for module in measured_modules:
        normalized_weight = (
            module["risk_weight_raw"] / total_raw_weight
            if risk_sources_available and total_raw_weight else None
        )
        module["risk_weight"] = (
            round(normalized_weight, 6) if normalized_weight is not None else None
        )
        module["risk_weight_percent"] = (
            round(normalized_weight * 100, 1) if normalized_weight is not None else None
        )

    weighted_coverage = (
        _weighted_scenario_percentage(measured_modules)
        if risk_sources_available else None
    )
    return {
        "status": (
            "available" if weighted_coverage is not None
            else "unavailable"
        ),
        "coverage_percent": (
            round(weighted_coverage, 1) if weighted_coverage is not None else None
        ),
        "formula": (
            "sum(normalized_module_risk_weight * scenario_coverage) * 100; "
            "normalized_module_risk_weight = raw_module_risk / sum(raw_module_risk)"
        ),
        "risk_weight_definition": (
            "raw_module_risk = 1 + recent_source_commits + "
            "severity_weighted_mapped_defects"
        ),
        "scenario_coverage_definition": (
            "covered_catalog_scenarios / total_catalog_scenarios; a scenario is covered "
            "only when every linked test case ran and passed"
        ),
        "weight_normalization": "Each included module's risk weight is divided by the sum of included raw weights.",
        "missing_risk_inputs": [
            name for name, available in (
                ("recent Git activity", git_data_available),
                ("mapped GitHub defect history", github_data_available),
            )
            if not available
        ],
        "measured_modules": len(measured_modules),
        "unmeasured_modules": len(unmeasured_modules),
        "modules": measured_modules,
        "excluded_modules": unmeasured_modules,
        "reason": None if weighted_coverage is not None else (
            "Cobertura indisponível: faltam cenários executados ou dados de risco."
        ),
    }
def get_coverage_analysis(days: int = 30) -> dict[str, Any]:
    """Combine measured coverage with GitHub defect and Git activity signals."""
    if days not in (7, 30, 90):
        raise ValueError("Period must be 7, 30, or 90 days.")
    coverage_data = get_test_coverage()
    repository_data: dict[str, Any] | None = None
    activity_error: str | None = None
    try:
        repository_data = get_repository_test_insights(days)
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        activity_error = f"Não foi possível ler a atividade do Git: {detail}"
    defect_history = get_github_defect_history()
    coverage_data["defect_history"] = defect_history
    activity_modules = repository_data["modules"] if repository_data else []
    annotate_file_attention(
        coverage_data["flows"],
        activity_modules,
        defect_history,
    )
    coverage_data["risk_weighted_scenario_coverage"] = (
        calculate_risk_weighted_scenario_coverage(
            coverage_data.get("test_outcomes", {}),
            activity_modules,
            defect_history,
            tests_run=coverage_data.get("tests_run", 0),
            git_data_available=repository_data is not None,
        )
    )
    coverage_data.pop("test_outcomes", None)
    if activity_error and coverage_data["risk_weighted_scenario_coverage"]["status"] == "unavailable":
        coverage_data["risk_weighted_scenario_coverage"]["reason"] = activity_error
    coverage_data["defect_prediction"] = {
        "status": "unavailable",
        "reason": (
            "O índice de atenção é heurístico; ainda não há um modelo de probabilidade "
            "treinado e validado cronologicamente."
        ),
    }
    coverage_data["analysis_period_days"] = days
    return coverage_data
