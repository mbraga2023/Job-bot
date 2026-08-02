# 🤖 Telegram QA Job Intelligence Bot

A Python automation platform that collects QA job opportunities from Telegram channels, extracts job information, scores opportunities based on personal preferences, validates application links, and prepares data for AI-based job analysis.

The goal is to transform raw job posts into actionable career intelligence.

---

# Features

## Job Collection

* 📥 Reads job posts from Telegram channels
* 🔍 Extracts job information automatically
* 🚫 Prevents duplicated jobs using Telegram message hashes
* 💾 Stores jobs in SQLite

## Job Processing

* 🏷 Classifies jobs by category
* ⭐ Scores opportunities using customizable rules
* 🚀 Detects remote opportunities
* 🔗 Extracts application links

## Link Validation

Using Playwright:

* Opens intermediary job platforms
* Validates application pages
* Extracts job details from platforms such as MeuPadrinho
* Prepares structured data for AI analysis

## AI Pipeline (in development)

Future agents:

* Job relevance analyzer
* Resume matching agent
* Application recommendation agent
* Career report generator

---

# Architecture

```
Telegram Channel
        |
        v
Telegram Collector
        |
        v
Parser
        |
        v
Classifier
        |
        v
Scorer
        |
        v
SQLite Database
        |
        +----------------+
        |                |
        v                v
Playwright        AI Agents
Validation        Analysis
        |
        v
Reports
```

---

# Tech Stack

* Python 3.11+
* Telethon
* SQLite
* Playwright
* OpenPyXL
* Pandas
* OpenAI API

---

# Project Structure

```
job-bot/

├── database/
│   └── jobs.db

├── output/
│   ├── jobs.xlsx
│   └── analysis.json

├── scripts/
│   ├── collect.bat
│   ├── validate.bat
│   ├── analyse.bat
│   └── full.bat

├── src/

│   ├── agents/
│   │   ├── analyzers/
│   │   ├── job_analyzer.py
│   │   ├── resume_matcher.py
│   │   └── report_agent.py

│   ├── commands/
│   │   ├── collect.py
│   │   ├── validate.py
│   │   ├── analyse.py
│   │   └── report.py

│   ├── database/
│   │   └── database.py

│   ├── models/
│   │   └── job.py

│   ├── services/
│   │   ├── browser_service.py
│   │   ├── database_service.py
│   │   ├── excel_service.py
│   │   ├── openai_service.py
│   │   └── telegram_service.py

│   ├── core/
│   │   ├── parser.py
│   │   ├── classifier.py
│   │   └── scorer.py

│   ├── config.py
│   └── main.py
```

---

# Installation

Clone:

```bash
git clone https://github.com/yourusername/job-bot.git

cd job-bot
```

Create environment:

```bash
python -m venv .venv
```

Activate:

Windows:

```bash
.venv\Scripts\activate
```

Install:

```bash
pip install -r requirements.txt
```

Install browsers:

```bash
playwright install
```

---

# Environment Variables

Create `.env`:

```env
API_ID=YOUR_API_ID
API_HASH=YOUR_API_HASH
OPENAI_API_KEY=YOUR_KEY
```

---

# Running

Main command:

```bash
python src/main.py
```

Available commands:

```bash
python src/main.py collect
python src/main.py validate
python src/main.py analyse
python src/main.py report
```

---

# Database

Main table:

```
jobs
```

Stores:

* title
* company
* location
* contract
* level
* link
* category
* score
* remote status

Future AI memory:

```
job_analysis
```

Stores:

* AI score
* recommendation
* matching skills
* missing skills
* analysis history

---

# Job Scoring

Jobs receive scores based on personal preferences.

Examples:

| Criteria       | Priority |
| -------------- | -------- |
| Remote         | High     |
| Pleno          | High     |
| QA Automation  | High     |
| Playwright     | High     |
| Cypress        | High     |
| API Testing    | Medium   |
| Manual QA only | Lower    |

---

# Duplicate Detection

Each Telegram message generates a unique hash:

```
Telegram Message
        |
        v
MD5 Hash
        |
        v
SQLite
```

Existing jobs are ignored.

---

# Roadmap

## Completed

* [x] Telegram integration
* [x] Job extraction
* [x] SQLite storage
* [x] Duplicate detection
* [x] Job classification
* [x] Job scoring
* [x] Excel export
* [x] Playwright validation
* [x] MeuPadrinho analyzer

## In Progress

* [ ] AI job relevance analysis
* [ ] Resume matching
* [ ] Application tracking
* [ ] Automated reports

## Future

* [ ] Dashboard
* [ ] Multi-channel support
* [ ] Salary extraction
* [ ] Company reputation analysis
* [ ] Personalized application messages

---

# License

MIT License

---

# Author

Michel Braga

Software Developer | QA Automation | Python | Java | Spring Boot | Playwright
