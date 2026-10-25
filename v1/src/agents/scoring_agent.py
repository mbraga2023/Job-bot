import json

from database.database import get_connection
from core.scorer import JobScorer


class ScoringAgent:

    def __init__(self):
        self.scorer = JobScorer()

    def get_jobs(self):

        with get_connection() as conn:

            cursor = conn.execute(
                """
                SELECT
                    jd.job_id,
                    jd.title,
                    jd.company,
                    jd.location,
                    jd.remote,
                    jd.level,
                    jd.technologies,
                    jd.job_status

                FROM job_details jd

                WHERE
                    jd.page_not_found = 0

                ORDER BY
                    jd.validated_at DESC
                """
            )

            return cursor.fetchall()

    @staticmethod
    def deserialize_technologies(value):

        if not value:
            return []

        if isinstance(value, list):
            return value

        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return parsed

        except json.JSONDecodeError:
            pass

        return [value]

    def save_score(
        self,
        job_id: int,
        score: int,
        reasons: list[str],
    ):

        with get_connection() as conn:

            conn.execute(
                """
                INSERT INTO job_ai_analysis (
                    job_id,
                    ai_score,
                    recommendation,
                    strengths,
                    analysis_version
                )

                VALUES (?, ?, ?, ?, 1)

                ON CONFLICT(job_id)
                DO UPDATE SET

                    ai_score = excluded.ai_score,

                    recommendation =
                        excluded.recommendation,

                    strengths =
                        excluded.strengths
                """,
                (
                    job_id,
                    score,
                    self.get_recommendation(score),
                    json.dumps(
                        reasons,
                        ensure_ascii=False,
                    ),
                ),
            )

            conn.commit()

    @staticmethod
    def get_recommendation(score):

        if score >= 100:
            return "HIGH"

        if score >= 70:
            return "GOOD"

        if score >= 40:
            return "POSSIBLE"

        return "LOW"

    def analyze(self):

        jobs = self.get_jobs()

        results = []

        for job in jobs:

            job_data = dict(job)

            job_data["technologies"] = (
                self.deserialize_technologies(
                    job_data["technologies"]
                )
            )

            score, reasons = self.scorer.score(
                job_data
            )

            self.save_score(
                job_id=job_data["job_id"],
                score=score,
                reasons=reasons,
            )

            results.append(
                {
                    "job_id": job_data["job_id"],
                    "title": job_data["title"],
                    "company": job_data["company"],
                    "score": score,
                    "reasons": reasons,
                }
            )

        return results

    def print_report(self):

        results = self.analyze()

        print()
        print("=" * 70)
        print("STAGE 3.3 - JOB SCORING")
        print("=" * 70)

        print(
            f"Jobs scored : {len(results)}"
        )

        print()

        if not results:

            print("No jobs found.")

            print("=" * 70)

            return

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        print(
            f"{'Score':>6}  "
            f"{'Company':<25} "
            f"Title"
        )

        print("-" * 70)

        for result in results:

            company = (
                result["company"]
                or ""
            )[:24]

            title = (
                result["title"]
                or ""
            )

            print(
                f"{result['score']:>6}  "
                f"{company:<25} "
                f"{title}"
            )

        print("=" * 70)