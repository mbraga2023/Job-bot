# database/job_status.py

DEFAULT_JOB_STATUS = "NEW"

JOB_STATUS = {
    "NEW",           # Validated, not reviewed yet
    "OPEN",          # Still accepting applications
    "CLOSED",        # No longer accepting applications
    "INTERESTED",    # Marked by user
    "APPLIED",       # Application submitted
    "INTERVIEW",     # Interview process
    "REJECTED",      # Rejected by company
    "ACCEPTED",      # Offer accepted
    "DISCARDED",     # Ignored by user
    "NOT_REMOTE",
    "MANUAL",        # Applied manually in the browser
    "linkedin_EasyApply",
}