# scorer.py

TECH_WEIGHTS = {

    # QA

    "qa": 20,
    "quality": 15,
    "qualidade": 20,

    "quality assurance": 20,

    "analista de qualidade": 20,
    "engenheiro de qualidade": 20,
    "controle de qualidade": 20,

    "quality analyst": 20,
    "quality engineer": 20,

    "teste": 20,
    "testes": 20,
    "testing": 20,
    "tester": 20,

    "software testing": 20,
    "software tester": 20,
    "software verification": 20,
    "verification": 15,

    "sdet": 25,

    # Automation

    "automação": 20,
    "automation": 20,
    "automatizado": 20,
    "automatização": 20,

    "playwright": 30,
    "cypress": 25,
    "selenium": 20,
    "robot framework": 20,
    "robot": 15,

    # API

    "api": 20,
    "rest": 15,
    "soap": 15,
    "postman": 15,
    "restassured": 15,

    # Languages

    "java": 15,
    "python": 10,
    ".net": 10,
    "c#": 10,

}


LOCATION_WEIGHTS = {

    "limeira": 40,
    "campinas": 35,
    "americana": 35,
    "piracicaba": 30,

    "remote": 35,
    "remoto": 35,

    "home office": 35,
    "home-office": 35,

    "100% remoto": 35,
    "100% remote": 35,

    "brasil remoto": 30,
    "brazil remote": 30,
    "anywhere in brazil": 30,

    "international": 50,
}


LEVEL_WEIGHTS = {

    "pleno": 30,

    "mid": 25,
    "middle": 25,

    "senior": 5,
    "sr": 5,

    "junior": -20,
    "jr": -20,
}


WORK_MODEL_WEIGHTS = {

    "hybrid": 5,
    "híbrido": 5,

    "presencial": -25,
    "on-site": -25,
}


def score_job(job):

    score = 0

    text = (
        job.get("raw_text")
        or ""
    ).lower()

    for keyword, weight in TECH_WEIGHTS.items():
        if keyword in text:
            score += weight

    for keyword, weight in LOCATION_WEIGHTS.items():
        if keyword in text:
            score += weight

    for keyword, weight in LEVEL_WEIGHTS.items():
        if keyword in text:
            score += weight

    for keyword, weight in WORK_MODEL_WEIGHTS.items():
        if keyword in text:
            score += weight

    if job.get("link"):
        score += 5

    return min(score, 100)