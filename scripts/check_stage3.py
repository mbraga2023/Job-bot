from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import database.database as db_mod
from database import schema
from database.database import get_connection
from agents.technology_agent import TechnologyAgent
import config


temp = Path(__file__).resolve().parent.parent / 'database' / 'test_stage3.db'
if temp.exists():
    temp.unlink()

db_mod.DB_PATH = temp
config.DATABASE = temp
schema.create_database()

with get_connection() as conn:
    conn.execute(
        "INSERT INTO jobs (id, telegram_hash, link, title, company, category) VALUES (?, ?, ?, ?, ?, ?)",
        (1, 'hash-a', 'https://example.com/a', 'QA Engineer', 'Acme', 'QA'),
    )
    conn.execute(
        "INSERT INTO jobs (id, telegram_hash, link, title, company, category) VALUES (?, ?, ?, ?, ?, ?)",
        (2, 'hash-b', 'https://example.com/b', 'QA Analyst', 'Acme', 'QA'),
    )
    conn.execute(
        "INSERT INTO job_details (job_id, page_not_found, title, company, location, remote, level, contract, job_source, application_url, application_source, description, technologies, requirements, differentials, benefits, job_status, ai_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, 0, 'QA Engineer', 'Acme', 'Remote', 1, 'Junior', 'CLT', 'meupadrinho', 'https://example.com/apply/1', 'meupadrinho', 'Build software', '["Playwright", "Python", "Playwright"]', '[]', '[]', '[]', 'NEW', 'PENDING'),
    )
    conn.execute(
        "INSERT INTO job_details (job_id, page_not_found, title, company, location, remote, level, contract, job_source, application_url, application_source, description, technologies, requirements, differentials, benefits, job_status, ai_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2, 0, 'QA Analyst', 'Acme', 'Remote', 1, 'Pleno', 'CLT', 'meupadrinho', 'https://example.com/apply/2', 'meupadrinho', 'Test software', '["Python", "Java"]', '[]', '[]', '[]', 'NEW', 'PENDING'),
    )
    conn.commit()

result = TechnologyAgent().analyze()
print(result['jobs_with_technologies'])
print(result['technologies']['PLAYWRIGHT'])
print(result['technologies']['PYTHON'])

try:
    temp.unlink()
except Exception:
    pass
