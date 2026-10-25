# commands/linkedin.py

import asyncio

from agents.linkedin_agent import run as linkedin


def run():

    asyncio.run(
        linkedin()
    )