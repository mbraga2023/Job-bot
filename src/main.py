#main.py
import argparse

from database.schema import create_database

from commands.collect import run as collect
from commands.validate import run as validate
from commands.analyse import run as analyse
from commands.report import run as report


COMMANDS = {
    "collect": collect,
    "validate": validate,
    "analyse": analyse,
    "report": report,
}


def main():

    parser = argparse.ArgumentParser(
        description="AI Job Search Assistant"
    )

    parser.add_argument(
        "command",
        choices=COMMANDS.keys()
    )

    args = parser.parse_args()
        # Create tables if they don't exist
    create_database()

    COMMANDS[args.command]()


if __name__ == "__main__":
    main()