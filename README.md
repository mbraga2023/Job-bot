# Job Bot

This project is a Python automation system for discovering QA jobs from public sources and storing the results in SQLite for later validation and review.

The project currently has two active extraction pipelines:

1. Telegram extraction
   - collects job posts from a configured Telegram channel,
   - parses the message content,
   - stores raw job records,
   - validates the original job link.

2. Companies career page extraction
   - imports company career page URLs,
   - scans those pages for job offers,
   - stores discovered job links in a dedicated table,
   - validates each career job page.

The analysis stage and the report stage are not ready yet. The codebase contains placeholders and experimental modules for those future steps, but they are not part of the currently working pipeline.

---

## Current status

The project is organized around active data collection and validation flows rather than a finished analysis/report system.

### Pipeline 1: Telegram extraction

This pipeline is responsible for reading Telegram job posts and turning them into structured raw job records.

Flow:

```text
Telegram channel
   ↓
collect
   ↓
jobs
   ↓
validate
   ↓
job_details
```

Main stages:
- collect raw messages from the configured Telegram channel,
- detect QA-relevant postings,
- discard duplicates,
- parse the message into structured fields,
- validate the job link and job page,
- store validated data in job_details.

### Pipeline 2: Companies career page extraction

This pipeline is responsible for discovering jobs from company career pages and validating those job listings.

Flow:

```text
career_sources
   ↓
careers
   ↓
career_jobs
   ↓
validate-career-jobs
   ↓
career_job_details
```

Main stages:
- import a list of career page URLs,
- open each company career page,
- find jobs that match QA-related criteria,
- store those jobs in career_jobs,
- validate each discovered application page,
- save the validated result in career_job_details.

---

## Environment setup

Create a .env file in the project root with:

```bash
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
TELEGRAM_CHANNEL=@your_channel_name
```

Then install the Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Main commands

```bash
python src/main.py collect
python src/main.py validate
python src/main.py import-careers
python src/main.py careers
python src/main.py validate-career-jobs
python src/main.py linkedin
python src/main.py analyse
python src/main.py report
```

The command dispatcher is in src/main.py. That file creates the database schema and routes each command to the matching module under src/commands.

The commands that are currently meaningful for the working pipelines are:
- collect
- validate
- import-careers
- careers
- validate-career-jobs

The commands related to analysis and reporting are still placeholders or incomplete work.

---

## Repository structure

```text
.
├── companies.txt
├── database/
│   └── jobs.db                     # SQLite database created at runtime
├── output/
│   ├── dashboard.html              # Generated dashboard output
│   └── job_analysis.json           # Analysis payload export (not complete yet)
├── scripts/
│   ├── analyse.bat
│   ├── collect.bat
│   ├── full.bat
│   ├── linkedin.bat
│   ├── report.bat
│   └── validate.bat
├── src/
│   ├── agents/
│   │   ├── analyzers/
│   │   │   ├── career.py
│   │   │   ├── career_jobs_links.py
│   │   │   ├── gupy.py
│   │   │   ├── linkedin.py
│   │   │   └── meupadrinho.py
│   │   ├── career_agent.py
│   │   ├── career_jobs_link_validator.py
│   │   ├── job_analyzer.py
│   │   ├── linkedin_agent.py
│   │   ├── report_agent.py
│   │   ├── resume_matcher.py
│   │   ├── technology_agent.py
│   │   ├── telegram_collector.py
│   │   └── link_validator.py
│   ├── commands/
│   │   ├── ai_analysis.py
│   │   ├── analyse.py
│   │   ├── career_jobs_link_validator.py
│   │   ├── careers.py
│   │   ├── collect.py
│   │   ├── detect_career_apis.py
│   │   ├── import_careers.py
│   │   ├── linkedin.py
│   │   ├── linkedin_connection_test.py
│   │   ├── normalize.py
│   │   ├── report.py
│   │   ├── resume_match.py
│   │   ├── score.py
│   │   ├── tech_report.py
│   │   ├── validate.py
│   │   └── __pycache__/
│   ├── core/
│   │   ├── career_result.py
│   │   ├── career_source.py
│   │   ├── classifier.py
│   │   ├── job_status.py
│   │   ├── parser.py
│   │   ├── scorer.py
│   │   └── technology_catalog.py
│   ├── data/
│   │   └── career_pages.json
│   ├── database/
│   │   ├── applications.py
│   │   ├── career_job_details.py
│   │   ├── career_jobs.py
│   │   ├── career_sources.py
│   │   ├── dashboard.py
│   │   ├── database.py
│   │   ├── job_analysis.py
│   │   ├── job_details.py
│   │   ├── jobs.py
│   │   ├── schema.py
│   │   └── __pycache__/
│   ├── services/
│   │   ├── browser_service.py
│   │   ├── career_source_importer.py
│   │   ├── excel_service.py
│   │   ├── html_service.py
│   │   ├── json_service.py
│   │   ├── linkedin_session.py
│   │   ├── openai_service.py
│   │   ├── telegram_service.py
│   │   └── __pycache__/
│   ├── config.py
│   ├── main.py
│   └── __pycache__/
├── storage/
│   └── linkedin_profile/
│       └── Browser and profile data for LinkedIn validation experiments
├── tests/
│   └── test_validation_fixes.py
├── companies.txt
├── job_bot_session.session
├── package.json
├── requirements.txt
├── README.md
└── .env
```

---

## File-by-file overview

### Root files

- package.json
  Minimal Node metadata. It is not part of the main Python runtime, but it keeps metadata consistent for any frontend or dependency tooling used around the project.

- requirements.txt
  Lists the Python dependencies needed to run the Telegram client, Playwright browser automation, SQLite access, JSON processing, and optional AI/report features.

- companies.txt
  A plain list of company names or identifiers that can be used as a reference while building the career source list.

- job_bot_session.session
  Telethon session file used to persist Telegram authentication between runs.

- README.md
  Project documentation and pipeline overview.

### src/main.py

Main CLI entry point. It defines the available commands, ensures the SQLite schema exists, and routes execution to the selected command module.

### src/config.py

Loads environment variables and holds project defaults like Telegram API credentials, channel name, output paths, browser headless mode, timeout values, and general app constants.

### src/commands

- collect.py
  Thin wrapper that calls the Telegram collector agent.

- validate.py
  Thin wrapper that calls the raw Telegram link validation flow.

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
  Defines the allowed job status values used throughout the project, such as NEW, OPEN, CLOSED, INTERESTED, APPLIED, INTERVIEW, REJECTED, ACCEPTED, DISCARDED, and NOT_REMOTE.

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
