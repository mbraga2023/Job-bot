"""Stage 3.2 entry point for technology frequency reporting."""

from agents.technology_agent import TechnologyAgent


def run():
    agent = TechnologyAgent()
    agent.print_report()


if __name__ == "__main__":
    run()
