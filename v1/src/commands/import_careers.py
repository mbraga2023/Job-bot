from pathlib import Path

from services.career_source_importer import (
    import_career_sources,
)


BASE_DIR = Path(__file__).resolve().parent.parent

JSON_PATH = BASE_DIR / "data" / "career_pages.json"


def run():

    print()
    print("=============================")
    print("Stage 1.2 - Import Career Sources")
    print("=============================")

    import_career_sources(
        JSON_PATH
    )


if __name__ == "__main__":
    run()