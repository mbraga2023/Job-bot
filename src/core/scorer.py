class JobScorer:

    def score(self, job: dict) -> tuple[int, list[str]]:

        score = 0
        reasons = []

        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()
        location = (job.get("location") or "").lower()
        level = (job.get("level") or "").lower()

        technologies = job.get("technologies") or []
        technologies = [
            str(technology).lower().strip()
            for technology in technologies
        ]

        remote = bool(job.get("remote", False))

        # =====================================================
        # REMOTE
        # =====================================================

        if remote:
            score += 60
            reasons.append("+60 Remote")

        # =====================================================
        # BRAZIL REMOTE
        # =====================================================

        if remote and any(
            country in location
            for country in (
                "brasil",
                "brazil",
            )
        ):
            score += 30
            reasons.append("+30 Brazil Remote")

        # =====================================================
        # PREFERRED CITY
        # =====================================================

        if "limeira" in location:
            score += 40
            reasons.append("+40 Limeira")

        elif "campinas" in location:
            score += 30
            reasons.append("+30 Campinas")

        elif "americana" in location:
            score += 30
            reasons.append("+30 Americana")

        elif "piracicaba" in location:
            score += 25
            reasons.append("+25 Piracicaba")

        # =====================================================
        # LEVEL
        # =====================================================

        if "pleno" in level or "mid" in level:
            score += 45
            reasons.append("+45 Pleno")

        elif (
            "junior" in level
            or "júnior" in level
            or "entry" in level
        ):
            score += 15
            reasons.append("+15 Junior")

        elif (
            "senior" in level
            or "sênior" in level
            or "sr." in level
            or "sr " in level
        ):
            score -= 35
            reasons.append("-35 Senior")

        # =====================================================
        # QA / QUALITY
        # =====================================================

        if (
            "qa" in title
            or "quality assurance" in title
            or "quality engineer" in title
            or "tester" in title
            or "test engineer" in title
        ):
            score += 25
            reasons.append("+25 QA / Testing")

        # =====================================================
        # AUTOMATION
        # =====================================================

        if (
            "automation" in title
            or any(
                "automation" in technology
                for technology in technologies
            )
        ):
            score += 30
            reasons.append("+30 Automation")

        # =====================================================
        # PLAYWRIGHT
        # =====================================================

        if any(
            "playwright" in technology
            for technology in technologies
        ):
            score += 40
            reasons.append("+40 Playwright")

        # =====================================================
        # CYPRESS
        # =====================================================

        if any(
            "cypress" in technology
            for technology in technologies
        ):
            score += 35
            reasons.append("+35 Cypress")

        # =====================================================
        # CUCUMBER / BDD
        # =====================================================

        if any(
            "cucumber" in technology
            or "bdd" in technology
            for technology in technologies
        ):
            score += 20
            reasons.append("+20 Cucumber / BDD")

        # =====================================================
        # SELENIUM
        # =====================================================

        if any(
            "selenium" in technology
            for technology in technologies
        ):
            score += 15
            reasons.append("+15 Selenium")

        # =====================================================
        # API TESTING
        # =====================================================

        if any(
            technology in (
                "api",
                "rest",
                "rest api",
                "rest assured",
            )
            or "api testing" in technology
            for technology in technologies
        ):
            score += 25
            reasons.append("+25 API Testing")

        # =====================================================
        # POSTMAN
        # =====================================================

        if any(
            "postman" in technology
            for technology in technologies
        ):
            score += 20
            reasons.append("+20 Postman")

        # =====================================================
        # JAVA
        # =====================================================

        if any(
            technology == "java"
            for technology in technologies
        ):
            score += 20
            reasons.append("+20 Java")

        # =====================================================
        # JAVASCRIPT
        # =====================================================

        if any(
            technology in (
                "javascript",
                "java script",
                "js",
            )
            for technology in technologies
        ):
            score += 20
            reasons.append("+20 JavaScript")

        # =====================================================
        # TYPESCRIPT
        # =====================================================

        if any(
            technology in (
                "typescript",
                "type script",
                "ts",
            )
            for technology in technologies
        ):
            score += 20
            reasons.append("+20 TypeScript")

        # =====================================================
        # PYTHON
        # =====================================================

        if any(
            technology == "python"
            for technology in technologies
        ):
            score += 10
            reasons.append("+10 Python")

        # =====================================================
        # CI/CD
        # =====================================================

        if any(
            technology in (
                "jenkins",
                "ci/cd",
                "ci cd",
                "cicd",
            )
            for technology in technologies
        ):
            score += 15
            reasons.append("+15 CI/CD")

        # =====================================================
        # JIRA
        # =====================================================

        if any(
            "jira" in technology
            for technology in technologies
        ):
            score += 10
            reasons.append("+10 Jira")

        # =====================================================
        # BROWSERSTACK
        # =====================================================

        if any(
            "browserstack" in technology
            for technology in technologies
        ):
            score += 10
            reasons.append("+10 BrowserStack")

        # =====================================================
        # DATABASE / SQL
        # =====================================================

        if any(
            technology in (
                "sql",
                "oracle",
                "postgres",
                "postgresql",
                "mysql",
                "mariadb",
            )
            for technology in technologies
        ):
            score += 10
            reasons.append("+10 Database / SQL")

        # =====================================================
        # MANUAL ONLY
        # =====================================================

        if (
            "manual" in title
            and "automation" not in title
        ):
            score -= 20
            reasons.append("-20 Manual Testing")

        # =====================================================
        # HYBRID
        # =====================================================

        if (
            "hybrid" in location
            or "híbrido" in location
            or "hibrido" in location
        ):
            score -= 25
            reasons.append("-25 Hybrid")

        # =====================================================
        # ON-SITE
        # =====================================================

        if (
            "on-site" in location
            or "onsite" in location
            or "on site" in location
            or "presencial" in location
        ):
            score -= 50
            reasons.append("-50 On-site")

        return score, reasons