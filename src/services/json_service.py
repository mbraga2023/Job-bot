#json_service.py
import json
from pathlib import Path


OUTPUT_FOLDER = Path("output")
OUTPUT_FOLDER.mkdir(exist_ok=True)

JSON_PATH = OUTPUT_FOLDER / "job_analysis.json"


def load_analysis():

    if not JSON_PATH.exists():
        return []

    with open(
        JSON_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def append_analysis(job):

    data = load_analysis()

    data.append(job)

    with open(
        JSON_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    return JSON_PATH


def save_analysis(data):

    with open(
        JSON_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    return JSON_PATH