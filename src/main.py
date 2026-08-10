import argparse

from commands.ai_analysis import run as ai_analysis
from commands.analyse import run as analyse
from commands.collect import run as collect
from commands.linkedin import run as linkedin
from commands.normalize import run as normalize
from commands.report import run as report
from commands.resume_match import run as resume_match
from commands.score import run as score
from commands.tech_report import run as tech_report
from commands.validate import run as validate
from database.schema import create_database


COMMANDS = {
    "collect": collect,
    "validate": validate,
    "linkedin": linkedin,
    "analyse": analyse,
    "normalize": normalize,
    "tech-report": tech_report,
    "score": score,
    "ai-analysis": ai_analysis,
    "resume-match": resume_match,
    "report": report,
}


def main():

    parser = argparse.ArgumentParser(
        description="AI Job Search Assistant"
    )

    parser.add_argument(
        "command",
        choices=COMMANDS.keys(),
        help="Pipeline stage to execute",
    )

    args = parser.parse_args()

    # Create database/tables if needed
    create_database()

    # Execute selected command
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()