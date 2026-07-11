# scorer.py

TECH_WEIGHTS = {

    # QA
    "qa": 20,
    "quality": 10,
    "tester": 20,
    "testes": 15,
    "test": 10,
    "sdet": 25,
    "quality assurance": 20,
    "analista de qualidade": 20,

    # Automation
    "automação": 20,
    "automation": 20,
    "playwright": 30,
    "cypress": 25,
    "selenium": 10,
    "robot": 15,
    "restassured": 15,
    "postman": 15,

    # API
    "api": 20,
    "rest": 15,
    "soap": 15,

    # Programming
    "java": 15,
    "python": 10,
    "c#": 10,
    ".net": 10,
}


LOCATION_WEIGHTS = {

    "limeira": 40,
    "campinas": 35,
    "americana": 35,
    "piracicaba": 30,

    "remote": 35,
    "remoto": 35,
    "home office": 35,
    "brasil remoto": 30,
    "brazil remote": 30,
    "international": 50,
}


LEVEL_WEIGHTS = {

    "pleno": 30,
    "mid": 25,
    "middle": 25,

    "senior": -10,

    "junior": -20,
    "jr": -20,
}


WORK_MODEL_WEIGHTS = {

    "hybrid": 5,
    "híbrido": 5,

    "on-site": -25,
    "presencial": -25,
}


def score_job(job):

    score = 0

    # Join all fields safely
    text = " ".join(
        str(value)
        for value in job.values()
        if value
    ).lower()


    # Technologies
    for keyword, weight in TECH_WEIGHTS.items():
        if keyword in text:
            score += weight


    # Location
    for keyword, weight in LOCATION_WEIGHTS.items():
        if keyword in text:
            score += weight


    # Level
    for keyword, weight in LEVEL_WEIGHTS.items():
        if keyword in text:
            score += weight


    # Work model
    for keyword, weight in WORK_MODEL_WEIGHTS.items():
        if keyword in text:
            score += weight


    # Link bonus
    if job.get("link"):
        score += 5


    return max(score, 0)