# =========================================================
# Technology normalization
# =========================================================

TECHNOLOGY_ALIASES = {

    # -----------------------------------------------------
    # Browser / UI automation
    # -----------------------------------------------------

    "PLAYWRIGHT": {
        "playwright",
        "playwright automation",
        "playwright framework",
        "playwright.js",
        "playwright js",
    },

    "CYPRESS": {
        "cypress",
        "cypress.io",
        "cypress io",
        "cypress framework",
    },

    "SELENIUM": {
        "selenium",
        "selenium webdriver",
        "selenium web driver",
    },

    "ROBOT FRAMEWORK": {
        "robot framework",
        "robotframework",
        "robot framework automation",
    },

    # -----------------------------------------------------
    # API testing
    # -----------------------------------------------------

    "API TESTING": {
        "api testing",
        "api tests",
        "api test",
        "rest api testing",
        "rest api",
        "restful api testing",
    },

    "POSTMAN": {
        "postman",
        "postman api",
    },

    "REST ASSURED": {
        "rest assured",
        "restassured",
    },

    # -----------------------------------------------------
    # Programming languages
    # -----------------------------------------------------

    "JAVA": {
        "java",
        "java 8",
        "java 11",
        "java 17",
        "java 21",
    },

    "PYTHON": {
        "python",
        "python 3",
        "python3",
    },

    "JAVASCRIPT": {
        "javascript",
        "java script",
        "js",
    },

    "TYPESCRIPT": {
        "typescript",
        "type script",
        "ts",
    },

    # -----------------------------------------------------
    # Frontend
    # -----------------------------------------------------

    "ANGULAR": {
        "angular",
        "angularjs",
        "angular 2+",
    },

    "REACT": {
        "react",
        "react.js",
        "reactjs",
        "react js",
    },

    # -----------------------------------------------------
    # Database
    # -----------------------------------------------------

    "SQL": {
        "sql",
        "sql server",
        "microsoft sql server",
        "t-sql",
        "tsql",
    },

    "POSTGRESQL": {
        "postgresql",
        "postgres",
        "postgre sql",
    },

    "MYSQL": {
        "mysql",
        "my sql",
    },

    # -----------------------------------------------------
    # DevOps / Cloud
    # -----------------------------------------------------

    "DOCKER": {
        "docker",
        "docker containers",
        "containerization",
    },

    "AWS": {
        "aws",
        "amazon web services",
    },

    "AZURE": {
        "azure",
        "microsoft azure",
    },

    "GIT": {
        "git",
    },

    "GITHUB": {
        "github",
        "github actions",
    },

    "JENKINS": {
        "jenkins",
    },

    # -----------------------------------------------------
    # QA methodologies
    # -----------------------------------------------------

    "BDD": {
        "bdd",
        "behavior driven development",
        "behaviour driven development",
    },

    "GHERKIN": {
        "gherkin",
    },

    "CICD": {
        "ci/cd",
        "ci cd",
        "cicd",
        "continuous integration",
        "continuous delivery",
        "continuous deployment",
    },
}


def normalize_technology(value: str) -> str | None:
    """
    Converts a technology variation into its canonical name.

    Example:

        playwright
        Playwright automation
        PLAYWRIGHT

    all become:

        PLAYWRIGHT
    """

    if not value:
        return None

    normalized = (
        value
        .strip()
        .lower()
    )

    for canonical, aliases in TECHNOLOGY_ALIASES.items():

        if normalized in aliases:
            return canonical

    return None