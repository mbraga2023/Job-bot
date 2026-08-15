from agents.career_agent import CareerAgent


async def run():

    agent = CareerAgent()

    await agent.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())