"""Stage 3.5 entry point for resume matching."""

from agents.resume_matcher import match


def resume_match(job_description):
    return match(job_description)


def run(job_description=None):
    if job_description is None:
        print("Stage 3.5 - provide a job description to match against a resume.")
        return None
    return resume_match(job_description)


if __name__ == "__main__":
    run()
