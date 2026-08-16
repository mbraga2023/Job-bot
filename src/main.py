import argparse
import asyncio
import inspect

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
from commands.careers import run as careers
from commands.import_careers import run as import_careers
from commands.detect_career_apis import (
    run as detect_career_apis,
)

from database.schema import create_database


COMMANDS = {
    "collect": collect,
    "validate": validate,
    "careers": careers,
    "linkedin": linkedin,

    "analyse": analyse,

    "normalize": normalize,
    "tech-report": tech_report,
    "score": score,

    "ai-analysis": ai_analysis,
    "resume-match": resume_match,

    "report": report,

    "import-careers": import_careers,

    "detect-career-apis": detect_career_apis,
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

    # Create/update database tables before running the command.
    create_database()

    command = COMMANDS[args.command]

    # Automatically handle both async and synchronous commands.
    if inspect.iscoroutinefunction(command):
        asyncio.run(command())
    else:
        command()


if __name__ == "__main__":
    main()