import argparse
import asyncio
import inspect

from commands.ai_analysis import run as ai_analysis
from commands.analyse import run as analyse
from commands.collect import run as collect
from commands.dashboard import run as dashboard
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
from commands.indeed import run as indeed

from commands.career_jobs_link_validator import (
    run as validate_career_jobs,
)
from commands.open_jobs import run as open_jobs
from commands.open_career_jobs import run as open_career_jobs

from database.schema import create_database


# =========================================================
# Commands
# =========================================================

COMMANDS = {

    # -----------------------------------------------------
    # Telegram job pipeline
    # -----------------------------------------------------

    "collect": collect,

    "validate": validate,

    "analyse": analyse,

    "normalize": normalize,

    "tech-report": tech_report,

    "score": score,

    "ai-analysis": ai_analysis,

    "resume-match": resume_match,

    "report": report,

    "dashboard": dashboard,

    "linkedin": linkedin,

    "indeed": indeed,

    "open-jobs": open_jobs,

    "open": open_jobs,

    "open-career-jobs": open_career_jobs,


    # -----------------------------------------------------
    # Career pipeline
    # -----------------------------------------------------

    "careers": careers,

    "import-careers": import_careers,

    "detect-career-apis": detect_career_apis,

    "validate-career-jobs": validate_career_jobs,
}


# =========================================================
# Main
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description="AI Job Search Assistant"
    )

    parser.add_argument(
        "command",
        choices=COMMANDS.keys(),
        help="Pipeline stage to execute",
    )

    parser.add_argument(
        "url",
        nargs="?",
        help="Optional parameter (e.g. Indeed URL, or limit/status for open-jobs)",
    )

    args = parser.parse_args()

    if args.command == "indeed" and not args.url:
        parser.error("the indeed command requires a job URL")

    # -----------------------------------------------------
    # Create/update database tables before running command.
    # -----------------------------------------------------

    if args.command != "indeed":
        create_database()

    # -----------------------------------------------------
    # Get command
    # -----------------------------------------------------

    command = COMMANDS[
        args.command
    ]

    # -----------------------------------------------------
    # Automatically handle both async
    # and synchronous commands.
    # -----------------------------------------------------

    if args.command in ("indeed", "open-jobs", "open"):

        if inspect.iscoroutinefunction(command):
            asyncio.run(command(args.url))
        else:
            command(args.url)

    elif inspect.iscoroutinefunction(command):

        asyncio.run(
            command()
        )

    else:

        command()


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":

    main()