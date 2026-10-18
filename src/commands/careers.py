import argparse

from agents.career_agent import CareerAgent


async def run(platform="search_all"):
    agent = CareerAgent(platform=platform)

    await agent.run()


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform",
        choices=("search_all", "inhire"),
        default="search_all",
    )
    asyncio.run(run(platform=parser.parse_args().platform))