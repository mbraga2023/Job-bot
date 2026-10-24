import html
from database.job_details import get_jobs_to_review, update_job_status
from services.browser_launcher import open_in_chrome

JOBS_PER_BATCH = 10


def run(arg: str | None = None):
    """
    Opens validated jobs with status OPEN and NEW in Google Chrome tabs.

    Usage:
        python src/main.py open-jobs         # Opens jobs 10 at a time
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

    valid_jobs = []
    for job in jobs:
        url = job.get("target_url")
        if not url:
            continue

        valid_jobs.append(job)

    if not valid_jobs:
        print("[!] No valid URLs found among retrieved jobs.\n")
        return

    for batch_start in range(0, len(valid_jobs), JOBS_PER_BATCH):
        batch = valid_jobs[batch_start:batch_start + JOBS_PER_BATCH]
        batch_number = batch_start // JOBS_PER_BATCH + 1
        total_batches = (len(valid_jobs) + JOBS_PER_BATCH - 1) // JOBS_PER_BATCH

        print(f"\nBatch {batch_number}/{total_batches}: {len(batch)} jobs")
        urls = []
        for index, job in enumerate(batch, start=batch_start + 1):
            raw_title = job.get("title") or "Untitled"
            title = html.unescape(raw_title).strip()
            company = html.unescape(job.get("company") or "Unknown").strip()
            status = job.get("job_status") or "NEW"

            print(f" [{index:02d}/{len(valid_jobs):02d}] [{status:<4}] {company} - {title}")
            print(f"        -> {job['target_url']}")
            urls.append(job["target_url"])

        print("=" * 65)
        success, message = open_in_chrome(urls)
        if not success:
            print(f"\n[X] {message}\n")
            return

        for job in batch:
            update_job_status(job["job_id"], "MANUAL")
        print(f"\n[OK] {message}")
        print(f"[OK] Marked {len(batch)} jobs as MANUAL.\n")

        if batch_start + JOBS_PER_BATCH < len(valid_jobs):
            input("Press Enter in the terminal to continue with the next 10 jobs...")


if __name__ == "__main__":
    run()
