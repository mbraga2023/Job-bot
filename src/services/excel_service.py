from pathlib import Path

import pandas as pd

OUTPUT_FOLDER = Path("output")


def latest_file():

    files = sorted(
        OUTPUT_FOLDER.glob("jobs_*.xlsx"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            "No jobs file found."
        )

    return files[0]


def read_jobs():

    file = latest_file()

    print(f"Reading {file.name}")

    return pd.read_excel(file)