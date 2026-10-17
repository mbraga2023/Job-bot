from datetime import datetime, timedelta, timezone
import unicodedata

from database.career_job_details import (
    get_new_career_job_details,
    update_career_job_status,
)


def _is_junior(level):
    normalized = unicodedata.normalize("NFKD", level or "")
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    ).casefold()
    return "junior" in normalized


def _is_older_than_30_days(validated_at, now=None):
    if not validated_at:
        return False

    try:
        validated = datetime.fromisoformat(str(validated_at).replace("Z", "+00:00"))
    except ValueError:
        print(
            f"[WARN] Could not parse career job validated_at "
            f"{validated_at!r}; leaving it NEW."
        )
        return False

    if validated.tzinfo is None:
        validated = validated.replace(tzinfo=timezone.utc)

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return now - validated > timedelta(days=30)


def discard_ineligible_new_career_jobs():
    """Discard NEW career jobs that are junior or were validated over 30 days ago."""
    discarded = {"junior": 0, "stale": 0}

    for job in get_new_career_job_details():
        if _is_junior(job.get("level")):
            reason = "junior"
        elif _is_older_than_30_days(job.get("validated_at")):
            reason = "stale"
        else:
            continue

        update_career_job_status(job["career_job_id"], "DISCARDED")
        discarded[reason] += 1
        print(
            f"[DISCARDED] {job.get('company') or 'Unknown'} - "
            f"{job.get('title') or 'Untitled'} ({reason})"
        )

    return discarded
