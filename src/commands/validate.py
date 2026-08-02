import asyncio

from agents.link_validator import run as validate


def run():

    asyncio.run(
        validate()
    )