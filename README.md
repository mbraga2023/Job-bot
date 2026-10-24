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
flows, database statistics, and command logs. The **Connect to Recruiters**
button is reserved for a future workflow.

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
python v2\main.py careers validate --limit 500
python v2\main.py careers open --limit 10
```

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

## Tests

Run the v2 test suite from the repository root:

```powershell
python -m unittest discover -s v2/tests
```
