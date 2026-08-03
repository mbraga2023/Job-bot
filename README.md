# 🤖 Telegram QA Job Intelligence Bot

A Python automation platform that collects QA job opportunities from
Telegram channels, validates application links, enriches job data, and
uses AI agents to generate career intelligence.

The project is organized as a multi-stage pipeline where each stage
stores structured data in SQLite and passes it to the next stage.

## Features

### Stage 1 --- Job Collection

-   📥 Collect jobs from Telegram channels
-   🔍 Parse job posts automatically
-   🏷 Classify jobs by category
-   ⭐ Score jobs using customizable rules
-   🚫 Prevent duplicates using Telegram message hashes
-   💾 Store raw jobs in the **jobs** table
-   📊 Export collected jobs to timestamped Excel files

### Stage 2 --- Link Validation

Using Playwright: - Open job links - Validate application pages -
Extract structured job information - Support MeuPadrinho (extensible to
other platforms) - Store validation results in **job_details** - Track
validation status (PENDING / VALIDATED / FAILED / NOT_FOUND)

### Stage 3 --- AI Analysis (In Progress)

-   AI relevance score
-   Summary
-   Strengths / Weaknesses
-   Skill matching
-   Recommendations
-   Versioned analysis history in **job_ai_analysis**

### Planned

-   Resume matching
-   Application tracking
-   Reports & Dashboard

## Architecture

``` text
Telegram
    │
    ▼
Collector
    │
    ▼
jobs
    │
    ▼
Playwright Validator
    │
    ▼
job_details
    │
    ▼
AI Analysis
    │
    ▼
job_ai_analysis
    │
    ▼
resume_matches
    │
    ▼
applications
```

## Project Structure

``` text
database/
scripts/
src/
├── agents/
        analysers/
            - meupadrinho.py
        - job_analyser.py (todo)
        - link_validator.py
        - report_agent.py (todo)
        - resume_matcher.py (todo)
        - telegram_collector.py
├── commands/
├── core/
    - classifier.py
    - parser.py
    - scorer.py
├── database/
│   ├── database.py
│   ├── schema.py
│   ├── jobs.py
│   ├── job_details.py
│   ├── job_analysis.py
│   ├── resume_matches.py (todo)
│   └── applications.py
├── services/
│   ├── telegram_service.py
│   ├── browser_service.py
│   ├── excel_service.py
│   └── json_service.py
    - openai_service.py (todo)
├── config.py
└── main.py
```

## Commands

``` bash
python src/main.py collect
python src/main.py validate
python src/main.py analyse
python src/main.py report
```

## Database

Tables: - jobs - job_details - job_ai_analysis - resume_matches -
applications

## View the SQLite database

Using the SQLite CLI:

``` bash
sqlite3 database/jobs.db
```

Useful commands:

``` sql
.tables
.schema jobs
.schema job_details

SELECT COUNT(*) FROM jobs;

SELECT id, score, company, title
FROM jobs
ORDER BY score DESC
LIMIT 10;

SELECT validation_status, COUNT(*)
FROM jobs
GROUP BY validation_status;

SELECT *
FROM job_details
LIMIT 5;

.quit
```

Or using Python:

``` bash
python
```

``` python
import sqlite3

conn = sqlite3.connect("database/jobs.db")

for row in conn.execute("SELECT id, company, title FROM jobs LIMIT 10"):
    print(row)
```

## Roadmap

### Completed

-   Telegram integration
-   SQLite multi-table architecture
-   Job parser
-   Classification & scoring
-   Duplicate detection
-   Excel export
-   Playwright validation
-   MeuPadrinho analyzer
-   Incremental validation pipeline

### In Progress

-   AI analysis
-   Resume matching
-   Application tracking
-   Reporting

### Future

-   Multi-platform analyzers
-   Salary extraction
-   Company intelligence
-   Dashboard
-   Cover letter generation

## Author

**Michel Braga**

Software Developer • QA Automation • Python • Java • Spring Boot •
Playwright
