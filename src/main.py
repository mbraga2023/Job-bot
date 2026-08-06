import argparse

from commands.analyse import run as analyse
from commands.collect import run as collect
from commands.report import run as report
from commands.validate import run as validate
from database.schema import create_database
from commands.linkedin import run as linkedin


COMMANDS = {
    "collect": collect,
    "validate": validate,
    "linkedin": linkedin,
    "analyse": analyse,
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