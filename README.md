# 🤖 Telegram QA Job Bot

A Python automation that monitors a Telegram jobs channel, extracts QA job opportunities, classifies them, scores them based on personal preferences, and exports everything to an Excel spreadsheet.

---

## Features

- 📥 Reads the latest job posts from a Telegram channel
- 🔍 Parses job information automatically
- 🏷 Classifies jobs by category
- ⭐ Scores jobs based on your preferences
- 🚀 Detects Remote/Home Office opportunities
- 🔗 Extracts application links
- 🌐 Resolves intermediary links (e.g. MeuPadrinho) to the original LinkedIn job (Playwright)
- 💾 Stores jobs in SQLite
- 📊 Exports all jobs to Excel
- 🚫 Avoids duplicate jobs using a Telegram message hash

---

## Tech Stack

- Python 3.11+
- Telethon
- SQLite
- OpenPyXL
- python-dotenv
- Playwright

---

## Project Structure

```
job-bot/
│
├── main.py                # Main application
├── parser.py              # Parses Telegram messages
├── classifier.py          # Classifies jobs
├── scorer.py              # Scores jobs
├── url_validator.py       # Resolves intermediary links
├── database.py            # SQLite operations
├── exporter.py            # Excel export
│
├── jobs.db
├── jobs.xlsx
├── .env
└── README.md
```

---

## Installation

Clone the repository.

```bash
git clone https://github.com/yourusername/job-bot.git

cd job-bot
```

Create a virtual environment.

### Windows

```bash
python -m venv .venv

.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv

source .venv/bin/activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Install Playwright browsers.

```bash
playwright install
```

---

## Environment Variables

Create a `.env` file.

```env
API_ID=YOUR_API_ID
API_HASH=YOUR_API_HASH
```

You can obtain these credentials from:

https://my.telegram.org

---

## Running

```bash
python main.py
```

The bot will:

1. Connect to Telegram
2. Read the latest messages
3. Parse QA jobs
4. Score each opportunity
5. Save new jobs to SQLite
6. Export everything to Excel

---

## Job Scoring

Each job receives a score based on predefined preferences.

Current priorities include:

| Criteria | Score |
|----------|------:|
| Remote | High |
| Hybrid | Medium |
| Pleno | High |
| Senior | Medium |
| Junior | Low |
| Limeira/SP | High |
| Campinas/SP | Medium |
| QA Automation | High |
| Manual QA | Medium |

The scoring system can be customized in `scorer.py`.

---

## Duplicate Detection

Each Telegram message generates an MD5 hash.

```text
Telegram Message
        ↓
MD5 Hash
        ↓
SQLite
```

If the hash already exists, the job is skipped.

---

## Link Resolution

Some Telegram posts contain intermediary websites such as:

```
Telegram
      ↓
meupadrinho.com.br
      ↓
LinkedIn Job
```

The bot uses Playwright to:

- Open the intermediary page
- Locate the **"Candidatar-se agora"** button
- Follow redirects
- Save the final LinkedIn job URL

This provides direct application links in the exported spreadsheet.

---

## Excel Output

Example:

| Score | Category | Remote | Title | Company | Level | Link |
|------:|----------|--------|-------|---------|-------|------|
| 95 | QA | Yes | QA Automation Analyst | Compass UOL | Senior | LinkedIn |
| 88 | QA | Yes | QA Engineer | CI&T | Pleno | LinkedIn |
| 75 | QA | No | Test Analyst | Stefanini | Junior | Company |

---

## Example Console Output

```
🚀 Starting Job Bot...

[095] QA | Compass UOL | QA Automation Analyst
[090] QA | CI&T | QA Engineer
[072] QA | Stefanini | Test Analyst

============================================================
📊 SUMMARY
============================================================
Messages scanned : 500
New jobs         : 41
Duplicates       : 459
Database records : 312
============================================================
```

---

## Roadmap

- [x] Telegram integration
- [x] SQLite database
- [x] Excel export
- [x] Job classification
- [x] Job scoring
- [x] Duplicate detection
- [x] Remote detection
- [x] Link extraction
- [ ] Playwright link resolver
- [ ] Multi-channel support
- [ ] Configurable scoring rules
- [ ] Daily email report
- [ ] Web dashboard
- [ ] AI-based job relevance scoring

---

## Future Improvements

- Multiple Telegram channels
- LinkedIn API integration
- Company reputation score
- Salary extraction
- Location normalization
- Automatic notifications
- Dashboard with filters
- Resume matching
- AI recommendations

---

## License

MIT License

---

## Author

Michel Braga
michel.diener@gmail.com

Software Developer | QA Automation | Python | Java | Spring Boot | Playwright