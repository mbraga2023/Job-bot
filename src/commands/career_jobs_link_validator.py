# /commands/career_jobs_link_validator.py

from agents.career_jobs_link_validator import run as validate_career_jobs_agent


async def run():
    """Validate career jobs through the real Playwright-based analyzer."""
    await validate_career_jobs_agent()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
