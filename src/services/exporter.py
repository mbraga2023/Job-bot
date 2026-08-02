import pandas as pd
from pathlib import Path
from datetime import datetime

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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_FOLDER / f"jobs_{timestamp}.xlsx"

    df.to_excel(output_file, index=False)

    print(f"\n✅ {len(df)} jobs exported to {output_file}")

    return output_file