import pandas as pd
from pathlib import Path
import time


OUTPUT_FOLDER = Path("output")
OUTPUT_FOLDER.mkdir(exist_ok=True)


def export_jobs(rows):

    columns = [
        "ID",
        "Score",
        "Category",
        "Remote",
        "Title",
        "Company",
        "Location",
        "Contract",
        "Level",
        "Applied",
        "Link",
        "Created At"
    ]

    df = pd.DataFrame(rows, columns=columns)

    df["Remote"] = df["Remote"].map({
        1: "Yes",
        0: "No"
    })

    df["Applied"] = df["Applied"].map({
        1: "Yes",
        0: "No"
    })


    df = df.sort_values(
        by=["Score", "Created At"],
        ascending=[False, False]
    )


    output_file = OUTPUT_FOLDER / "jobs.xlsx"


    # Retry if Excel has the file locked
    for attempt in range(3):

        try:
            df.to_excel(
                output_file,
                index=False
            )

            print(
                f"\n✅ {len(df)} jobs exported to {output_file}"
            )
            return

        except PermissionError:

            print(
                "⚠️ jobs.xlsx is locked. Close Excel..."
            )

            time.sleep(3)


    raise PermissionError(
        "Could not write jobs.xlsx. "
        "Please close Excel and try again."
    )