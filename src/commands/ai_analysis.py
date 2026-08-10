"""Stage 3.4 entry point for AI job analysis."""

from agents.job_analyzer import run as analyze_job


def run():
    return analyze_job()


if __name__ == "__main__":
    run()
