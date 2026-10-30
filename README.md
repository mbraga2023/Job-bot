# Job Bot

Job Bot automates job discovery, validation, and review through Telegram job
channels and company career pages. The current application entry point is the
v2 CLI at `v2\main.py`.

## Requirements

- Python 3.10+
- Google Chrome for LinkedIn and job review flows
- Microsoft Edge for Telegram job validation (Chromium fallback is used if Edge
  is unavailable)
- Telegram API credentials and channel configuration for the Telegram flow
- Ollama running locally for AI-based career-job validation

## Setup

From the repository root, create and activate a virtual environment, then
install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file in the repository root for Telegram collection:

```dotenv
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
TELEGRAM_CHANNEL=your_channel_name_or_id
```

Optional settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_SESSION` | `job_bot_session` | Telegram session filename |
| `HEADLESS` | `true` | Run browser flows without showing the browser |
| `TIMEOUT` | `30000` | Browser navigation timeout in milliseconds |
| `VALIDATE_DELAY_MIN` | `2.5` | Minimum delay between Telegram validations |
| `VALIDATE_DELAY_MAX` | `5.0` | Maximum delay between Telegram validations |
| `VALIDATION_LIMIT` | `500` | Default number of Telegram jobs to validate |
| `OLLAMA_MODEL` | `qwen2.5-coder:1.5b` | Local model used for QA job-title classification |
| `GITHUB_TOKEN` | unset | Optional read-only GitHub token used by Test Insights to read issues, merged PRs, and changed files |
| `GITHUB_REPOSITORY` | `mbraga2023/Job-bot` | Repository slug used for GitHub issue history (`owner/repository`) |
| `GITHUB_DEFECT_LABELS` | `bug,defect,defeito` | Comma-separated issue labels/types treated as defects |

The v2 database is initialized automatically at `database\jobs_v2.db` when a
CLI command is run.

## Main entry points

Run commands from the repository root:

```powershell
python v2\main.py --help
```

### Dashboard

Start the local dashboard at `http://127.0.0.1:8766/`:

```powershell
python v2\main.py dashboard
```

Options:

```powershell
python v2\main.py dashboard --port 9000
python v2\main.py dashboard --no-browser
```

The dashboard provides controls for the Telegram/LinkedIn and company-career
flows, database statistics, and command logs. It also shows whether the local
Ollama API is online and can start Ollama when it is offline. This indicates
that the Ollama service responds; the Python client must also be installed in
the interpreter running the dashboard. The dashboard launcher prefers the
project's `.venv`, and the badge reports if its Python client is missing. The **CLOSE**
button stops any active dashboard command and the Ollama process listening on
port 11434, then shuts down the dashboard server. The dashboard verifies the
listener is `ollama` before stopping it. Browser settings may prevent the
dashboard tab from closing automatically; if so, close it manually.
The **Connect to Recruiters** button is reserved for a future workflow.

The **Test Insights** tab (`/test-insights`) uses the repository's Git history
to display recent code changes by area and lists existing related v2 test
files. These are change-activity indicators, not defect probabilities.
Test outcomes are measured on demand; the dashboard does not retain historical
test-run results. Optional GitHub issue integration can enrich risk analysis
when configured.
The **Cobertura de código** card runs the v2 unit-test suite on request and
measures line and branch coverage across v2 production code with `coverage.py`.
It reports the test run's failure/error counts alongside coverage, and breaks
the results down by file for the career and Telegram/LinkedIn flows. Branch
coverage is unavailable for files without measured branches.

The dashboard also displays **risk-weighted scenario coverage**, separately
from line and branch coverage. Its initial, explicit scenario inventory is
`SCENARIO_CATALOG` in `v2/dashboard/insights.py`; each scenario is linked to
one or more existing unit-test cases. A scenario counts as covered only when
all linked tests ran and passed. Failed, skipped, or absent linked tests do not
count as covered. If the suite has not run, scenario coverage is `N/D`, not
100%. The catalog is an initial, reviewable scope—not an automatically
complete inventory of every product requirement—and should be maintained as
requirements and tests change.

For module *i*, scenario coverage `C_i` is its covered catalog scenarios
divided by its total catalog scenarios. The raw module risk is
`1 + recent source commits + severity-weighted mapped defects`. The displayed
normalized module weight `R_i` is its raw risk divided by the sum of raw risks
for included modules. Risk coverage is
`sum(R_i * C_i) * 100`. If a risk source is unavailable, the dashboard lists
that missing input; if both Git and mapped GitHub defect data are unavailable,
the weighted KPI is `N/D`. Modules without measured scenario coverage are
excluded from the weighted calculation and reported separately.

The per-file attention map is a different heuristic:
`risk_weight * uncovered_line_fraction`, normalized to 0–100 against the
highest-scoring measured file. It is not a coverage metric or a defect
probability. GitHub defects are counted only when a bug-labeled closed issue
is linked by a closing keyword to a merged PR, and the file was changed by
that PR. Severity weights are 5 for Critical/P0, 3 for High/P1, 2 for
Medium/P2, and 1 when no severity label is present.

The illustrative Payment processing (50, 80%), Authentication (30, 60%),
and User profile (20, 100%) example calculates to 78%. It is a unit-test
fixture only and is never used as production dashboard data.

To enable GitHub history, set a **read-only, repository-scoped** `GITHUB_TOKEN`
in the root `.env` or the dashboard process environment. Grant read access to
Issues and Pull requests. The token is sent only to `api.github.com`, is never
returned by the dashboard, and must not be committed or pasted into chat.
Set `GITHUB_DEFECT_LABELS` to match the repository's actual bug labels if
needed. Issue-to-file links are considered reliable only through merged PR
closing references; unmapped issues remain unknown.

Risk weights are transparent prioritization signals, not validated
probabilities. When the local Ollama service is available, the dashboard sends
the measured module aggregates (scenario and line/branch coverage, recent
commit counts, mapped-defect severity when available, and catalogued gaps) to
the configured `OLLAMA_MODEL` for a concise qualitative testing-priority
review. It does not send source code or issue text. The model must ground
recommendations in those measurements; its output is labeled as AI-assisted
analysis, never as a defect probability or a validated prediction. If Ollama
is offline or returns invalid output, the dashboard reports the analysis as
unavailable and preserves the deterministic coverage and risk metrics.
Missing GitHub access or issue mappings are listed as missing inputs, not
silently treated as zero mapped defects.

### Telegram and LinkedIn flow

Run each stage independently:

```powershell
python v2\main.py telegram collect --limit 500
python v2\main.py telegram validate --limit 500
python v2\main.py telegram linkedin --limit 100
python v2\main.py telegram open --limit 10
```

- `collect` imports structured job messages from the configured Telegram
  channel without filtering by job title. New records remain unclassified.
- `validate` extracts job details, then applies three deterministic gates
  before calling Ollama: QA-related title (including the non-QA exclusion
  list), confirmed remote work, and acceptable seniority. Only jobs that pass
  all three gates receive the final Ollama review, which cross-checks the title
  against extracted technologies. QA tools such as Selenium, Playwright,
  Cypress, and ISTQB provide strong QA evidence. Junior, senior, internship,
  and trainee roles retain their specific seniority discard reasons. If the
  final review fails, the job remains pending for a later retry.
- `linkedin` checks LinkedIn job links, application status, and workplace mode.
  LinkedIn member profile links are marked `RECRUITER`.
- `open` opens only explicitly remote Telegram jobs for review, up to 10 per
  run. Hybrid, onsite, unknown-work-mode, and `RECRUITER` records are excluded.

Explicitly excluded titles include Monitor de Qualidade, Gerente Executivo de
Qualidade, Consultor de Validação, Especialista em Desenvolvimento do Produto,
Pesquisador, Inspetor de qualidade, Analista de sistemas de gestão, Analista de
Controle de Qualidade Pleno, Analista de negócios, Analista de Monitoramento,
Gestão de qualidade, and Assistente de qualidade.

### Company career pages

```powershell
python v2\main.py careers import path\to\sources.json
python v2\main.py careers detect-apis --limit 500
python v2\main.py careers scan --platform search_all
python v2\main.py careers scan --platform inhire
python v2\main.py careers scan --platform gupy
python v2\main.py careers validate --limit 500
python v2\main.py careers open --limit 10
```

The dashboard's Career Pages flow can scan all sources, InHire sources only, or
Gupy sources only. Gupy-only scans match source URLs containing `gupy.io` and
search the top QA terms using Gupy's live search field.
During validation, Gupy job pages are parsed for localized title, dates,
location, job type, work model, description, and requirements before the
extracted details are passed to the LLM for its final QA/seniority decision.

Career source JSON must be an array of objects with a `company` and
`careers_url`. `search_url` and `source_type` are optional:

```json
[
  {
    "company": "Example Company",
    "careers_url": "https://example.com/careers",
    "search_url": "https://example.com/careers?query=qa",
    "source_type": "CAREER_PAGE"
  }
]
```

### Database statistics

```powershell
python v2\main.py stats
```

## Windows shortcuts

Batch files are available under `v2\scripts\`:

- `dashboard.bat` — launches the dashboard
- `telegram_flow.bat` — runs the Telegram collection, validation, LinkedIn
  check, and review sequence
- `career_flow.bat` — scans, validates, and opens eligible career-page jobs

## Project layout

```text
v1/                           # Legacy application, tests, and Windows shortcuts
├── src/                      # Original application code
├── scripts/                  # Original Windows shortcuts and utilities
└── tests/                    # Original test suite
v2/
├── config.py                 # Environment and application settings
├── main.py                   # CLI entry point
├── core/                     # Database, browser, date, and classification helpers
├── dashboard/                # Local web dashboard
├── flows/
│   ├── careers/              # Career source import, scanning, and validation
│   └── telegram/             # Telegram and LinkedIn workflows
├── scripts/                  # Windows flow shortcuts
└── tests/                    # Automated tests
```

The original v1 CLI remains available at `v1\src\main.py`; run it from the
repository root so it continues to use the shared root-level database and
configuration. Its Windows shortcuts are in `v1\scripts\`.

## Tests

Run the v2 test suite from the repository root:

```powershell
python -m unittest discover -s v2/tests
```

Run the v1 test suite from PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\v1\src"
python -m unittest discover -s v1/tests
```
