import re


class CareerApiDetector:

    # Positive indicators that an endpoint may contain jobs
    JOB_PATTERNS = {
        r"/jobs?([/?]|$)": 10,
        r"/vagas?([/?]|$)": 10,
        r"/vacanc(y|ies)([/?]|$)": 10,
        r"/opportunit(y|ies)([/?]|$)": 10,
        r"/positions?([/?]|$)": 8,
        r"/openings?([/?]|$)": 8,
        r"/careers?([/?]|$)": 5,
        r"/search([/?]|$)": 8,
        r"/list([/?]|$)": 5,
        r"/faceted[_-]?search": 8,
        r"/job[_-]?search": 15,
        r"/searchjobs": 15,
        r"/search[_-]?jobs": 15,
        r"/jobboard": 10,
    }

    # Things that are usually unrelated to jobs
    IGNORE_PATTERNS = {
        r"linkedin\.com": -30,
        r"googleads": -30,
        r"doubleclick": -30,
        r"google\.com/recaptcha": -30,
        r"youtube\.com": -30,
        r"maps\.googleapis\.com": -30,
        r"analytics": -25,
        r"tracking": -25,
        r"track": -20,
        r"pixel": -25,
        r"consent": -20,
        r"captcha": -30,
        r"survicate": -20,
        r"handtalk": -20,
        r"auth": -15,
        r"login": -15,
        r"dictionary": -5,
        r"config": -5,
        r"settings": -5,
        r"schema": -5,
    }

    def __init__(self):

        self.responses = []

    async def detect(
        self,
        page,
        url,
    ):

        self.responses = []

        async def handle_response(response):

            try:

                request = response.request

                resource_type = request.resource_type

                content_type = (
                    response.headers.get(
                        "content-type",
                        "",
                    ).lower()
                )

                if resource_type not in {
                    "xhr",
                    "fetch",
                }:
                    return

                if "json" not in content_type:
                    return

                api_url = response.url

                score = self.score_api_url(
                    api_url
                )

                self.responses.append(
                    {
                        "method": request.method,
                        "status": response.status,
                        "url": api_url,
                        "content_type": content_type,
                        "score": score,
                    }
                )

            except Exception:
                pass

        page.on(
            "response",
            handle_response,
        )

        try:

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            # Allow client-side applications to
            # perform their initial API requests.
            await page.wait_for_timeout(5000)

            platform = await self.detect_platform(
                page
            )

            # Highest score first
            self.responses.sort(
                key=lambda item: item["score"],
                reverse=True,
            )

            best_api = self.get_best_candidate()

            return {
                "platform": platform,
                "responses": self.responses,
                "best_api": best_api,
            }

        finally:

            page.remove_listener(
                "response",
                handle_response,
            )

    def score_api_url(
        self,
        url: str,
    ) -> int:

        value = url.lower()

        score = 0

        # Positive job-related patterns
        for pattern, points in self.JOB_PATTERNS.items():

            if re.search(
                pattern,
                value,
            ):
                score += points

        # Negative/non-job patterns
        for pattern, points in self.IGNORE_PATTERNS.items():

            if re.search(
                pattern,
                value,
            ):
                score += points

        return score

    def get_best_candidate(self):

        if not self.responses:
            return None

        candidates = [
            response
            for response in self.responses
            if response["score"] > 0
        ]

        if not candidates:
            return None

        # Highest score wins.
        # If scores are equal, prefer successful responses.
        candidates.sort(
            key=lambda item: (
                item["score"],
                1 if 200 <= item["status"] < 300 else 0,
            ),
            reverse=True,
        )

        return candidates[0]

    async def detect_platform(
        self,
        page,
    ):

        current_url = page.url.lower()

        # GUPY
        if "gupy.io" in current_url:
            return "GUPY"

        gupy_search = page.locator(
            '[data-testid="job-search"]'
        )

        if await gupy_search.count() > 0:
            return "GUPY"

        # PANDAPE
        if "pandape" in current_url:
            return "PANDAPE"

        # QUICKIN
        if "quickin" in current_url:
            return "QUICKIN"

        # KENOBY
        if "kenoby" in current_url:
            return "KENOBY"

        # VAGAS
        if "vagas.com.br" in current_url:
            return "VAGAS"

        # ENTER
        if "enter.jobs" in current_url:
            return "ENTER"

        # JOBDIVA
        if "jobdiva.com" in current_url:
            return "JOBDIVA"

        # FLAIR
        if "flair.hr" in current_url:
            return "FLAIR"

        return "UNKNOWN"