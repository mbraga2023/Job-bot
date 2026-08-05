#telegram_service.py
import hashlib
import re

from telethon import TelegramClient

from config import API_ID, API_HASH, TELEGRAM_CHANNEL


class TelegramService:

    def __init__(self):

        self.client = TelegramClient(
            "job_bot_session",
            API_ID,
            API_HASH
        )

    async def connect(self):

        await self.client.start()

    async def disconnect(self):

        await self.client.disconnect()

    async def get_channel(self):

        return await self.client.get_entity(
            TELEGRAM_CHANNEL
        )

    async def iter_messages(self, limit=500):

        channel = await self.get_channel()

        async for message in self.client.iter_messages(
            channel,
            limit=limit
        ):
            yield message


def extract_link(message):
    """
    Extract URL from Telegram message.

    Supports:
    1. Visible URLs in message text
    2. Hidden clickable entities
    3. Inline keyboard buttons
    """

    text = message.text or ""

    # -------------------------
    # URLs written in text
    # -------------------------

    urls = re.findall(
        r"https?://[^\s)]+",
        text
    )

    if urls:
        return urls[0].rstrip(".,]")

    # -------------------------
    # Hidden entities
    # -------------------------

    if message.entities:

        for entity in message.entities:

            url = getattr(
                entity,
                "url",
                None
            )

            if url:
                return url

    # -------------------------
    # Inline keyboard buttons
    # -------------------------

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
        for key, value in job.items()
        if value and key not in {"link", "telegram_hash"}
    ).lower()

    keywords = (
        "remoto",
        "remota",
        "remote",
        "home office",
        "home-office",
    )

    return any(
        keyword in text
        for keyword in keywords
    )


def generate_hash(text):

    return hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()