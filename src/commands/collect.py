import asyncio

from agents.telegram_collector import run as collect


def run():

    asyncio.run(
        collect()
    )