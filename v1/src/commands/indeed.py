from agents.indeed_agent import run as inspect_indeed_job


async def run(url: str | None = None):
    if not url:
        raise ValueError(
            "Provide an Indeed URL or saved HTML file: "
            "python v1/src/main.py indeed <URL-or-HTML-file>"
        )

    await inspect_indeed_job(url)