##classifier.py
QA_KEYWORDS = (

    "qa",

    "quality",

    "qualidade",

    "teste",
    "testing",
    "tester",

    "software testing",

    "software verification",

    "quality assurance",

    "sdet",

    "playwright",
    "cypress",
    "selenium",
)


def classify(job):

    text = (
        job.get("raw_text")
        or ""
    ).lower()

    for keyword in QA_KEYWORDS:
        if keyword in text:
            return "QA"

    return "OTHER"