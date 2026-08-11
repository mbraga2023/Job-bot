"""Stage 3.3 entry point for job scoring."""

from agents.scoring_agent import ScoringAgent


def run():

    agent = ScoringAgent()

    agent.print_report()


if __name__ == "__main__":
    run()