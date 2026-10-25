from telethon import TelegramClient

from config import API_ID, API_HASH, TELEGRAM_CHANNEL

from core.parser import parse_job
from core.classifier import classify

from services.telegram_service import (
    extract_link,
    generate_hash,
    is_remote,
)

from database.jobs import (
    job_exists_by_link,
    insert_job,
    get_all_jobs,
)

from services.excel_service import export_jobs


async def run():

    print("\n🚀 Starting Telegram Collector...\n")

    client = TelegramClient(
        "job_bot_session",
        API_ID,
        API_HASH,
    )

    await client.start()

    channel = await client.get_entity(
        TELEGRAM_CHANNEL
    )

    total_messages = 0
    new_jobs = 0
    duplicated_jobs = 0

    async for message in client.iter_messages(
        channel,
        limit=500,
    ):

        total_messages += 1

        if not message.text:
            continue

        if "Título" not in message.text:
            continue

        job = parse_job(message.text)

        job["link"] = extract_link(message)

        if not job["link"]:
            continue

        job["category"] = classify(job)

        job["remote"] = is_remote(job)

        # Keep the hash for traceability
        job["telegram_hash"] = generate_hash(message.text)

        # -------------------------------------------------
        # Skip duplicated job links
        # -------------------------------------------------

        if job_exists_by_link(job["link"]):
            duplicated_jobs += 1
            continue

        insert_job(job)

        new_jobs += 1

        print(
            f"{job['category']:<5} | "
            f"{'REMOTE' if job['remote'] else 'ONSITE':<7} | "
            f"{job['company']} | "
            f"{job['title']}"
        )

    rows = get_all_jobs()

    export_jobs(rows)

    print("\n" + "=" * 60)
    print("📊 COLLECTION SUMMARY")
    print("=" * 60)
    print(f"Messages scanned : {total_messages}")
    print(f"New jobs         : {new_jobs}")
    print(f"Duplicates       : {duplicated_jobs}")
    print(f"Database records : {len(rows)}")
    print("=" * 60)

    await client.disconnect()