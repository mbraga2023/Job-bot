"""Stage 3.3 entry point for the scoring heuristic."""

from core.scorer import score_job


def score(job: dict):
    return score_job(job)


def run(job: dict | None = None):
    if job is None:
        print("Stage 3.3 - scoring is handled by core.scorer.score_job().")
        return None
    return score(job)


if __name__ == "__main__":
    run()
