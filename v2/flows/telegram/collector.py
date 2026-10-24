"""Telegram Job Collector for v2."""

from __future__ import annotations

import asyncio
from telethon import TelegramClient

from v2.config import config
from v2.core.database import insert_discovered_job
from v2.core.qa_classifier import is_qa_title
from v2.flows.telegram.parser import (
    extract_message_link,
    generate_telegram_hash,
    is_remote_job,
    parse_job_message,
)


async def run_collector(limit: int = 500) -> dict[str, int]:
    """Scan Telegram channel for job postings and save new jobs in centralized DB."""
    print("\n" + "=" * 60)
    print("[TELEGRAM] Starting Collector...")
    print("=" * 60)

    session_path = str(config.root_dir / config.telegram.session_name)
    client = TelegramClient(
        session_path,
        config.telegram.api_id,
        config.telegram.api_hash,
    )

    await client.start()

    try:
        channel = await client.get_entity(config.telegram.channel)

        total_messages = 0
        new_jobs = 0
        duplicates = 0
        skipped = 0

        async for message in client.iter_messages(channel, limit=limit):
            total_messages += 1
            text = getattr(message, "text", "") or ""

            if "Título" not in text:
                skipped += 1
                continue

            parsed = parse_job_message(text)
            link = extract_message_link(message)

            if not link:
                skipped += 1
                continue

            category = "QA" if await is_qa_title(parsed.get("title")) else "OTHER"
            remote = is_remote_job(parsed)
            msg_hash = generate_telegram_hash(text)

            job_id = insert_discovered_job(
                pipeline="TELEGRAM",
                source_url=link,
                title=parsed.get("title"),
                company=parsed.get("company"),
                location=parsed.get("location"),
                remote=remote,
                level=parsed.get("level"),
                contract=parsed.get("contract"),
                category=category,
                telegram_hash=msg_hash,
            )

            if job_id:
                new_jobs += 1
                print(f" [+] {category:<5} | {'REMOTE' if remote else 'ONSITE':<7} | {parsed.get('company')} | {parsed.get('title')}")
            else:
                duplicates += 1

        print("\n" + "=" * 60)
        print("[SUMMARY] TELEGRAM COLLECTION METRICS")
        print("=" * 60)
        print(f" Messages scanned : {total_messages}")
        print(f" New jobs added   : {new_jobs}")
        print(f" Duplicates seen  : {duplicates}")
        print(f" Skipped messages : {skipped}")
        print("=" * 60 + "\n")

        return {
            "scanned": total_messages,
            "new": new_jobs,
            "duplicates": duplicates,
            "skipped": skipped,
        }

    finally:
        await client.disconnect()


def run(limit: int = 500) -> None:
    """Synchronous entry point."""
    asyncio.run(run_collector(limit=limit))
