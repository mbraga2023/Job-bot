# Job Bot

Job Bot is a Python automation project for collecting, filtering, validating, and reviewing QA-focused job opportunities from Telegram and company career pages. It stores structured job records in SQLite and exposes a small CLI to run each stage of the pipeline.

This project is not a finished SaaS product; it is a workflow-oriented job intelligence bot with working collection and validation stages, plus several additional modules that are partial or experimental.

---

## What the project does

The codebase currently implements two main pipelines:

1. Telegram job collection
   - reads job messages from a configured Telegram channel,
   - parses the message payload,
   - extracts links and metadata,
   - classifies entries as QA or OTHER,
   - removes duplicates,
   - stores raw jobs in SQLite,
   - validates the job link and fills a details table.

2. Career-page discovery
   - imports career sources from a JSON list,
   - scans company career pages with Playwright,
   - extracts QA-related jobs,
   - saves the discovered URLs to a dedicated table,
   - validates them individually and keeps the result in a second details table.

The project also contains several exploratory stages for scoring, AI analysis, dashboard generation, and technology reporting, but some of those commands are still lightweight wrappers or incomplete implementations.

---

## Runtime architecture

The main entry point is [src/main.py](src/main.py). It does three important things:

- defines the CLI command map,
- ensures all database tables exist before execution,
- dispatches to the requested module by name.

The database schema is built in [src/database/schema.py](src/database/schema.py). It creates the following tables:

- jobs
- job_details
- job_ai_analysis
- resume_matches
- career_sources
- career_jobs
- career_job_details

The project relies on SQLite, Playwright, Telethon, Python-dotenv, and a few data-processing libraries. The main environment and defaults are configured in [src/config.py](src/config.py).

---

## Environment setup

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Create a .env file

Create a file named .env at the project root:

```env
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
TELEGRAM_CHANNEL=@your_channel_name
```

The app uses these values to connect to Telegram and read messages from the target channel.

### 3) Confirm Python version

The code uses modern Python syntax such as `str | None` type hints and `asyncio`, so a Python 3.10+ runtime is expected.

---

## Database and output paths

The configuration currently sets:

- database file: `database/jobs.db`
- output folder: `output/`
- dashboard output: `output/dashboard.html`
- analysis export: `output/job_analysis.json`

The SQLite connection factory is implemented in [src/database/database.py](src/database/database.py). It enables foreign keys and creates a Row-based connection for easier data access.

---

## Core workflows

### Telegram collection

Flow:

```text
Telegram channel
  -> parse message
  -> extract link and metadata
  -> classify QA/OTHER
  -> deduplicate by link
  -> insert into jobs
  -> export jobs list
```

Relevant files:

- [src/agents/telegram_collector.py](src/agents/telegram_collector.py)
- [src/core/parser.py](src/core/parser.py)
- [src/core/classifier.py](src/core/classifier.py)
- [src/database/jobs.py](src/database/jobs.py)
- [src/services/telegram_service.py](src/services/telegram_service.py)

### Job validation

The validation stage opens the job page with Playwright and scrapes structured data, including title, company, level, contract, description, and technologies when available. Jobs with a senior level are filtered out by design, and a page-not-found or closed-state result is recorded.

Relevant files:

- [src/agents/link_validator.py](src/agents/link_validator.py)
- [src/agents/analyzers/meupadrinho.py](src/agents/analyzers/meupadrinho.py)
- [src/database/job_details.py](src/database/job_details.py)
- [src/services/json_service.py](src/services/json_service.py)

### Career page discovery

The career flow imports company sources from [src/data/career_pages.json](src/data/career_pages.json), scans each page with Playwright, stores the discovered job URLs, and later validates those job pages in a second pass.

Relevant files:

- [src/commands/import_careers.py](src/commands/import_careers.py)
- [src/services/career_source_importer.py](src/services/career_source_importer.py)
- [src/agents/career_agent.py](src/agents/career_agent.py)
- [src/database/career_sources.py](src/database/career_sources.py)
- [src/database/career_jobs.py](src/database/career_jobs.py)
- [src/agents/career_jobs_link_validator.py](src/agents/career_jobs_link_validator.py)

---

## CLI commands

The dispatcher is defined in [src/main.py](src/main.py). The available commands are:

```bash
python src/main.py collect
python src/main.py validate
python src/main.py analyse
python src/main.py normalize
python src/main.py tech-report
python src/main.py score
python src/main.py ai-analysis
python src/main.py resume-match
python src/main.py report
python src/main.py linkedin
python src/main.py indeed <indeed-job-url>
python src/main.py open-jobs [limit|status]
python src/main.py careers
python src/main.py import-careers
python src/main.py detect-career-apis
python src/main.py validate-career-jobs
python src/main.py dashboard
```

### Functional / active flows

These are the commands that align with the working collection and validation code:

```bash
python src/main.py collect
python src/main.py validate
python src/main.py open
python src/main.py dashboard
python src/main.py import-careers
python src/main.py careers
python src/main.py validate-career-jobs
python src/main.py report
```

### Partial / experimental modules

These commands are present but not fully implemented or are early-stage utilities:

- `analyse` -> simple placeholder
- `normalize` -> entry point only
- `tech-report` -> technology reporting logic exists
- `score` -> scoring agent exists
- `ai-analysis` -> analysis entry point exists
- `resume-match` -> placeholder only
- `linkedin` -> wrapper to LinkedIn workflow
- `detect-career-apis` -> discovery helper for career APIs

---

## Typical usage

### 1) Collect Telegram job posts

```bash
python src/main.py collect
```

This reads the configured Telegram channel, parses job messages, and writes valid entries to the `jobs` table.

### 2) Validate pending jobs

```bash
python src/main.py validate
```

This fetches pending jobs from the validation queue, opens each listing with Playwright, and stores the detailed results in `job_details`.

### 3) Import career sources

```bash
python src/main.py import-careers
```

This loads the company list from [src/data/career_pages.json](src/data/career_pages.json) into the `career_sources` table.

### 4) Scan career pages

```bash
python src/main.py careers
```

This uses Playwright to examine each active company career page and collect links to QA-related jobs.

### 5) Validate discovered career jobs

```bash
python src/main.py validate-career-jobs
```

This revisits the discovered career links and writes details to `career_job_details`.

### 6) Run the local dashboard

```bash
python src/main.py dashboard
```

This starts the Job Bot dashboard at `http://127.0.0.1:8765/` and opens it in
your browser. Its first button row groups Collect, Validate, LinkedIn, and Open
jobs for the Telegram/LinkedIn flow; the second row groups Careers and Open
career jobs. Use **Stop command** to terminate the currently running command.
Only one command runs at a time. Set `JOB_BOT_DASHBOARD_PORT` to choose another
port.

The separate `report` command still generates a static jobs table at
`output/dashboard.html`.

### 7) Open active jobs in browser tabs

```bash
python src/main.py open-jobs
```

Opens all validated jobs with status `OPEN` and `NEW` as separate tabs in a dedicated Google Chrome window (or default browser).

Status-specific browser commands:
```bash
python src/main.py open-jobs OPEN    # Opens only jobs verified as OPEN
python src/main.py open-jobs NEW     # Opens only jobs with status NEW

python src/main.py open-jobs 10      # Opens the top 10 jobs
```

On Windows, you can also run [`scripts/open_jobs.bat`](scripts/open_jobs.bat) directly.

### Inspect an Indeed listing

```bash
python src/main.py indeed https://www.indeed.com/viewjob?jk=your-job-id
```

This experimental, read-only command prints extracted job details, description, and relevant links to the console. It does not save records to the database.

---

## Project layout

```text
.
├── README.md
├── requirements.txt
├── package.json
├── .env.example (not present in repo, created by user)
├── companies.txt
├── job_bot_session.session
├── database/
│   └── jobs.db                  # created at runtime
├── output/
│   ├── dashboard.html
│   └── job_analysis.json
├── scripts/
│   ├── collect.bat
│   ├── validate.bat
│   ├── analyse.bat
│   ├── report.bat
│   ├── linkedin.bat
│   └── full.bat
├── src/
│   ├── agents/
│   ├── commands/
│   ├── core/
│   ├── data/
│   ├── database/
│   ├── services/
│   ├── config.py
│   ├── main.py
│   └── __pycache__/
├── storage/
│   └── linkedin_profile/
└── tests/
    └── test_validation_fixes.py
```

---

## Notes and caveats

- This repository is strongly tied to QA job discovery and not a general-purpose job scraper.
- Duplicate filtering is based on URLs and Telegram hashes.
- Data quality is maintained through validation stages, but not every command is mature or actively used.
- Browser automation is done with Playwright and may require a working browser runtime in the local environment.
- The dashboard is HTML-based and generated from the database rather than from a UI framework.

---

## Summary

The real working engine in this project is:

```text
Telegram channel / career sources
  -> collect
  -> parse + classify
  -> deduplicate
  -> validate
  -> store in SQLite
  -> optionally generate reports/dashboard
```

If you want to extend the project, the most natural next steps are:

1. finish the AI-analysis pipeline,
2. complete the resume-match feature,
3. improve the reporting and score threshold logic,
4. add a cleaner CLI and better configuration management.

- import_careers.py
  Reads the career source JSON file and inserts company career pages into the career_sources table.

- careers.py
  Runs the career page agent that scans company pages and stores discovered jobs in career_jobs.

- detect_career_apis.py
  Experimental command for detecting API-based career source formats; not the active production path.

- career_jobs_link_validator.py
  Entry point for validating discovered career job links and saving their details.

- linkedin.py
  LinkedIn validation workflow entry point; still partial and not considered stable.

- analyse.py
  Placeholder analysis command. It is not ready and should not be treated as part of the working pipeline.

- report.py
  Reporting/dashboard command. This is still incomplete and not the active deliverable right now.

- ai_analysis.py
  Experimental entry point for AI-based analysis logic.

- normalize.py
  Helper command for normalizing data and repair workflows.

- score.py
  Command hook for scoring jobs or matches based on heuristics.

- tech_report.py
  Utility command related to technology extraction/reporting; still experimental.

- resume_match.py
  Command for resume-to-job matching; not fully integrated into the active pipeline.

- linkedin_connection_test.py
  Small utility used to check whether LinkedIn access or page structure is usable in the current environment.

### src/agents

- telegram_collector.py
  Runs the Telegram extraction pipeline. It connects to the configured channel, reads messages, extracts the job link, classifies the posting as QA or not, filters duplicates, and inserts raw jobs into the database.

- link_validator.py
  Validates the Telegram-derived job links, checks if the job page is still valid, and writes structured details into job_details.

- career_agent.py
  Scans configured company career pages, detects QA-relevant job links, and stores them in career_jobs while marking old entries as inactive when they disappear.

- career_jobs_link_validator.py
  Loads pending career jobs, opens each application page in a browser, extracts the relevant details, applies discard rules for senior positions, and saves the validated result in career_job_details.

- job_analyzer.py
  AI-oriented analysis workflow for job understanding. It exists as a future step, not the active pipeline.

- report_agent.py
  Placeholder for report-generation logic. Not used in the current active workflow.

- resume_matcher.py
  Intended for resume-to-job compatibility evaluation. Still provisional.

- technology_agent.py
  Intended to classify or summarize technologies mentioned in jobs. Not part of the current stable pipeline.

- linkedin_agent.py
  LinkedIn-specific validation and enrichment flow; still partial and dependent on page access quality.

- analyzers/career.py
  Extracts job links from a company career page and decides which ones are relevant to QA work.

- analyzers/career_jobs_links.py
  Loads a job detail page and extracts the actual job information from a company application page.

- analyzers/gupy.py
  Specialized parser for Gupy-powered job pages.

- analyzers/linkedin.py
  LinkedIn page analyzer for job validation or metadata extraction.

- analyzers/meupadrinho.py
  Specialized parser for job links or pages that pass through MeuPadrinho redirects.

### src/core

- classifier.py
  Checks whether a job is related to QA by scanning for keywords such as qa, quality, test, automation, and similar terms.

- parser.py
  Normalizes Telegram job text and extracts title, company, location, role, contract, level, and description fields.

- scorer.py
  Applies a weighted heuristic score to rank jobs by relevance and matching criteria.

- job_status.py
  Defines the allowed job status values used throughout the project, such as NEW, OPEN, CLOSED, MANUAL (applied manually in the browser), INTERESTED, APPLIED, INTERVIEW, REJECTED, ACCEPTED, DISCARDED, and NOT_REMOTE.

- technology_catalog.py
  Stores or references technology keywords used by technology-related classification features.

- career_result.py
  Represents a parsed result from the career-page discovery workflow.

- career_source.py
  Represents a company career source entry, including URL and metadata about the source.

### src/services

- telegram_service.py
  Provides helpers for Telegram message parsing, link extraction, remote detection, hash generation, and related text cleanup.

- browser_service.py
  Wraps Playwright browser/page behavior so the app can open, wait, and navigate pages reliably.

- career_source_importer.py
  Imports JSON career source data into the database and validates the structure before insertion.

- excel_service.py
  Exports job rows to spreadsheet-friendly output.

- html_service.py
  Builds the dashboard HTML page that summarizes job data.

- json_service.py
  Appends or persists JSON analysis data used by analysis-oriented workflows.

- openai_service.py
  Integration point for OpenAI-based AI analysis and prompting logic.

- linkedin_session.py
  Supports LinkedIn session handling and browser state needed for validation experiments.

### src/database

- database.py
  Central SQLite connection helper. It opens and returns the database connection used across the project.

- schema.py
  Creates all database tables used by the Telegram and career pipelines.

- jobs.py
  CRUD layer for the raw jobs table. Stores Telegram-discovered jobs before validation.

- job_details.py
  Stores validated Telegram job details after a link has been checked and enriched.

- job_analysis.py
  Persistence layer for the AI analysis output associated with jobs.

- applications.py
  Tracks application state or user actions for jobs.

- dashboard.py
  Queries used to build dashboard summaries and reports.

- career_sources.py
  Manages the list of tracked company career pages and their source metadata.

- career_jobs.py
  Stores discovered jobs from company career pages before validation.

- career_job_details.py
  Stores the validated results for career-page jobs, including source URL normalization and job-status assignment.

### tests

- test_validation_fixes.py
  Regression tests for validation and parsing fixes. This is the closest thing to a maintained safety net in the current codebase.

---

## Notes about the current project direction

The project is not yet a finished end-to-end AI recruiting platform.

The codebase already contains the foundations for:
- Telegram extraction,
- career page extraction,
- validation workflows,
- SQLite persistence,
- browser-based validation,
- dashboard output.

But the stage that would turn this into a complete analysis/reporting system is still under construction. At the moment, the reliable and active parts are the two collection pipelines described above.

The intended future direction is to continue from the validated records and add:
- richer AI analysis,
- better job scoring,
- resume-to-job matching,
- improved reporting and source quality monitoring.
