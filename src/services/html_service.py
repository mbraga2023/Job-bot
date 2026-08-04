from pathlib import Path

from database.dashboard import get_dashboard_jobs


OUTPUT = Path("output/dashboard.html")


STATUS_OPTIONS = [
    "NEW",
    "INTERESTED",
    "APPLIED",
    "INTERVIEW",
    "REJECTED",
    "ACCEPTED",
    "DISCARDED",
]


def generate_dashboard():

    jobs = get_dashboard_jobs()


    rows = ""


    for job in jobs:

        remote = "YES" if job["remote"] else "NO"

        page_status = (
            "FOUND"
            if not job["page_not_found"]
            else "REMOVED"
        )


        options = ""

        for status in STATUS_OPTIONS:

            selected = (
                "selected"
                if job["status"] == status
                else ""
            )

            options += f"""
                <option value="{status}" {selected}>
                    {status}
                </option>
            """


        rows += f"""

        <tr>

            <td class="score">
                {job["score"]}
            </td>


            <td>
                {job["published_date"] or "-"}
            </td>


            <td>
                {job["category"]}
            </td>


            <td>
                {job["title"]}
            </td>


            <td>
                {job["company"]}
            </td>


            <td>
                {job["location"]}
            </td>


            <td>
                {job["level"]}
            </td>


            <td>
                {remote}
            </td>


            <td>
                {page_status}
            </td>


            <td>

                <select
                    onchange="updateStatus(
                        {job['id']},
                        this.value
                    )"
                >

                    {options}

                </select>

            </td>


            <td>

                <a
                    href="{job["link"]}"
                    target="_blank"
                >
                    Open
                </a>

            </td>


        </tr>

        """



    html = f"""

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">


<title>
AI Job Dashboard
</title>


<style>

body {{

    font-family: Arial, sans-serif;

    margin: 30px;

}}


h1 {{

    margin-bottom:20px;

}}


table {{

    width:100%;

    border-collapse:collapse;

}}


th {{

    background:#222;

    color:white;

    padding:10px;

    text-align:left;

}}


td {{

    padding:8px;

    border-bottom:1px solid #ddd;

}}


tr:hover {{

    background:#f4f4f4;

}}


.score {{

    font-weight:bold;

    text-align:center;

}}


select {{

    padding:5px;

}}


a {{

    text-decoration:none;

}}


</style>


</head>


<body>


<h1>
AI Job Search Dashboard
</h1>


<p>
Total jobs: {len(jobs)}
</p>



<table>


<thead>

<tr>

<th>
Score
</th>


<th>
Published
</th>


<th>
Category
</th>


<th>
Title
</th>


<th>
Company
</th>


<th>
Location
</th>


<th>
Level
</th>


<th>
Remote
</th>


<th>
Page_found
</th>


<th>
Status
</th>


<th>
Link
</th>


</tr>

</thead>


<tbody>


{rows}


</tbody>


</table>



<script>


function updateStatus(jobId, status) {{

    console.log(
        "Update job:",
        jobId,
        status
    );


    /*
        Future API:

        fetch(
            `/jobs/${{jobId}}/status`,
            {{
                method:"PATCH",

                headers:{{
                    "Content-Type":
                    "application/json"
                }},

                body: JSON.stringify({{
                    status:status
                }})
            }}
        )

    */

}}


</script>


</body>

</html>

"""


    OUTPUT.parent.mkdir(
        exist_ok=True
    )


    OUTPUT.write_text(
        html,
        encoding="utf-8"
    )


    return OUTPUT