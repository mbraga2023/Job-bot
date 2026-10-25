# classifier.py

QA_KEYWORDS = (

    "qa",

    "quality",

    "quality assurance",

    "quality engineer",

    "quality analyst",

    "software quality",

    "test",

    "tester",

    "testing",

    "teste",

    "test analyst",

    "test engineer",

    "automation",

    "automação",

    "sdet",

)


def classify(job):

    text = " ".join(

        str(v)

        for v in job.values()

        if v

    ).lower()

    if any(keyword in text for keyword in QA_KEYWORDS):
        return "QA"

    return "OTHER"