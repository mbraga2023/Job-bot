#json_service.py
import json

from config import OUTPUT_FOLDER


OUTPUT_FOLDER.mkdir(exist_ok=True)
JSON_PATH = OUTPUT_FOLDER / "job_analysis.json"


def _record_key(job):
    source_data = job.get("source_data") if isinstance(job, dict) else None
    if isinstance(source_data, dict):
        if source_data.get("id") is not None:
            return ("id", source_data["id"])
        if source_data.get("link"):
            return ("link", source_data["link"])
    return json.dumps(job, sort_keys=True, ensure_ascii=False)


def load_analysis():

    if not JSON_PATH.exists():
        return []

    with open(
        JSON_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []


def append_analysis(job):

    data = load_analysis()
    seen = {_record_key(item) for item in data}
    key = _record_key(job)

    if key not in seen:
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
