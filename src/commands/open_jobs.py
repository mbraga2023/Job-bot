import html
from database.job_details import get_jobs_to_review
from services.browser_launcher import open_in_chrome


def run(arg: str | None = None):
    """
    Opens validated jobs with status OPEN and NEW in Google Chrome tabs.

    Usage:
        python src/main.py open-jobs         # Opens all OPEN and NEW jobs
        python src/main.py open-jobs 10      # Opens top 10 jobs
        python src/main.py open-jobs OPEN    # Opens only OPEN jobs
        python src/main.py open-jobs NEW     # Opens only NEW jobs
    """
    statuses = ("OPEN", "NEW")
    limit = None

    if arg:
        arg_clean = arg.strip().upper()
        if arg_clean.isdigit():
            limit = int(arg_clean)
        elif arg_clean in ("OPEN", "NEW"):
            statuses = (arg_clean,)
        elif "," in arg_clean:
            parts = tuple(p.strip() for p in arg_clean.split(",") if p.strip())
            if parts:
                statuses = parts

    jobs = get_jobs_to_review(statuses=statuses, limit=limit)

    if not jobs:
        print("\n" + "=" * 60)
        print(" [!] No matching jobs found to open.")
        print(f"     Target statuses: {', '.join(statuses)}")
        print("     Tip: Run 'validate' and 'linkedin' first to gather active jobs.")
        print("=" * 60 + "\n")
        return

    print("\n" + "=" * 65)
    print(f" OPENING JOBS IN CHROME BROWSER ({len(jobs)} jobs)")
    print(f" Target Statuses: {', '.join(statuses)}")
    print("=" * 65)

    urls = []
    for index, job in enumerate(jobs, start=1):
        url = job.get("target_url")
        if not url:
            continue

        raw_title = job.get("title") or "Untitled"
        title = html.unescape(raw_title).strip()
        company = html.unescape(job.get("company") or "Unknown").strip()
        status = job.get("job_status") or "NEW"

        print(f" [{index:02d}/{len(jobs):02d}] [{status:<4}] {company} - {title}")
        print(f"        -> {url}")
        urls.append(url)

    print("=" * 65)

    if not urls:
        print("[!] No valid URLs found among retrieved jobs.\n")
        return

    success, message = open_in_chrome(urls)
    if success:
        print(f"\n[OK] {message}\n")
    else:
        print(f"\n[X] {message}\n")


if __name__ == "__main__":
    run()
