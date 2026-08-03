from pathlib import Path
from datetime import datetime

import pandas as pd


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
        "Created At",
    ]
    
    data = [
    {
        "ID": row["id"],
        "Score": row["score"],
        "Category": row["category"],
        "Remote": row["remote"],
        "Title": row["title"],
        "Company": row["company"],
        "Location": row["location"],
        "Contract": row["contract"],
        "Level": row["level"],
        "Applied": row["applied"],
        "Link": row["link"],
        "Created At": row["created_at"],
    }
    for row in rows
]

    df = pd.DataFrame(rows, columns=columns)

    df["Remote"] = df["Remote"].map({
        1: "Yes",
        0: "No",
    })

    df["Applied"] = df["Applied"].map({
        1: "Yes",
        0: "No",
    })

    df = df.sort_values(
        by=["Score", "Created At"],
        ascending=[False, False],
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = OUTPUT_FOLDER / f"jobs_{timestamp}.xlsx"

    df.to_excel(output_file, index=False)

    print(f"\n✅ {len(df)} jobs exported to {output_file}")

    return output_file


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