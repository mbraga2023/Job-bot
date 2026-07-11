import hashlib
import os
import re

from dotenv import load_dotenv
from telethon import TelegramClient

from parser import parse_job
from classifier import classify
from scorer import score_job

from database import (
    create_database,
    job_exists,
    insert_job,
    get_all_jobs,
)

from exporter import export_jobs


load_dotenv()


api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

CHANNEL = "[CANAL] Vagas para Qa👨‍💻"


client = TelegramClient(
    "job_bot_session",
    api_id,
    api_hash
)



def extract_link(message):
    """
    Extract URL from Telegram message.

    Supports:
    1. Visible URLs in message text
    2. Hidden clickable text entities
    3. Inline keyboard buttons below the message
    """

    text = message.text or ""


    # --------------------------------
    # 1 - URL written directly in text
    # --------------------------------

    urls = re.findall(
        r"https?://\S+",
        text
    )

    if urls:
        return urls[0]



    # --------------------------------
    # 2 - Hidden clickable entities
    # Example:
    # "Apply here" -> https://company.com/job
    # --------------------------------

    if message.entities:

        for entity in message.entities:

            url = getattr(
                entity,
                "url",
                None
            )

            if url:
                return url



    # --------------------------------
    # 3 - Telegram inline keyboard
    # Example:
    # [Apply]
    # [View Job]
    # --------------------------------

    if message.reply_markup:

        for row in message.reply_markup.rows:

            for button in row.buttons:

                url = getattr(
                    button,
                    "url",
                    None
                )

                if url:
                    return url



    return None





def is_remote(job):

    text = " ".join(
        str(value)
        for value in job.values()
        if value
    ).lower()


    return (
        "remoto" in text
        or "remote" in text
        or "home office" in text
        or "brasil" in text
    )





async def main():

    print("\n🚀 Starting Job Bot...\n")


    create_database()



    channel = await client.get_entity(
        CHANNEL
    )


    total_messages = 0
    new_jobs = 0
    duplicated_jobs = 0



    async for message in client.iter_messages(
        channel,
        limit=500
    ):


        total_messages += 1



        # Ignore messages without text

        if not message.text:
            continue



        # Only process job posts

        if "Título" not in message.text:
            continue




        # ---------------------
        # Parse
        # ---------------------

        job = parse_job(
            message.text
        )




        # ---------------------
        # Extract Telegram link
        # ---------------------

        link = extract_link(
            message
        )

        job["link"] = link



        print(
            "🔗 LINK:",
            link
        )




        # ---------------------
        # Category
        # ---------------------

        job["category"] = classify(
            job
        )




        # ---------------------
        # Score
        # ---------------------

        job["score"] = score_job(
            job
        )




        # ---------------------
        # Remote
        # ---------------------

        job["remote"] = is_remote(
            job
        )




        # ---------------------
        # Hash
        # ---------------------

        job["telegram_hash"] = hashlib.md5(
            message.text.encode("utf-8")
        ).hexdigest()




        # ---------------------
        # Duplicate
        # ---------------------

        if job_exists(
            job["telegram_hash"]
        ):

            duplicated_jobs += 1
            continue





        # ---------------------
        # Save
        # ---------------------

        insert_job(
            job
        )

        new_jobs += 1




        print(
            f"[{job.get('score',0):03}] "
            f"{job.get('category','OTHER'):<5} | "
            f"{job.get('company','Unknown')} | "
            f"{job.get('title','No title')}"
        )





    # ---------------------
    # Export Excel
    # ---------------------

    rows = get_all_jobs()


    export_jobs(
        rows
    )




    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    print(
        f"Messages scanned : {total_messages}"
    )

    print(
        f"New jobs         : {new_jobs}"
    )

    print(
        f"Duplicates       : {duplicated_jobs}"
    )

    print(
        f"Database records : {len(rows)}"
    )

    print("=" * 60)





with client:

    client.start()

    client.loop.run_until_complete(
        main()
    )