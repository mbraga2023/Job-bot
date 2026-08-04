##classifier.py
def classify(job):

    title = job["title"].lower()

    if "qa" in title:
        return "QA"

    if "quality" in title:
        return "QA"

    if "teste" in title:
        return "QA"

    if "sdet" in title:
        return "QA"

    if "automation" in title:
        return "QA"

    return "OTHER"