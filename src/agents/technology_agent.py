import json
from collections import Counter

from database.database import get_connection
from core.technology_catalog import normalize_technology


class TechnologyAgent:

    @staticmethod
    def _normalize_technology_list(raw_value):
        """Accept either a JSON list, a Python list, or a plain string."""
        if raw_value is None:
            return []

        if isinstance(raw_value, list):
            return raw_value

        if isinstance(raw_value, str):
            value = raw_value.strip()
            if not value:
                return []

            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

            return [part.strip() for part in value.split(",") if part.strip()]

        return [str(raw_value)]

    def get_jobs(self):

        with get_connection() as conn:

            cursor = conn.execute(
                """
                SELECT
                    job_id,
                    title,
                    company,
                    level,
                    technologies

                FROM job_details

                WHERE
                    LOWER(COALESCE(level, '')) IN ('junior', 'pleno')

                    AND page_not_found = 0

                ORDER BY
                    validated_at DESC
                """
            )

            return cursor.fetchall()

    def analyze(self):

        jobs = self.get_jobs()

        technology_counter = Counter()

        analyzed_jobs = 0

        for job in jobs:

            technologies = self._normalize_technology_list(
                job["technologies"]
            )

            if not technologies:
                continue

            analyzed_jobs += 1

            for technology in technologies:

                normalized = normalize_technology(
                    str(technology)
                )

                if normalized:
                    technology_counter[normalized] += 1

        return {
            "total_jobs": len(jobs),
            "jobs_with_technologies": analyzed_jobs,
            "technologies": technology_counter,
        }

    def print_report(self):

        result = self.analyze()

        total_jobs = result["total_jobs"]
        analyzed_jobs = result["jobs_with_technologies"]
        technologies = result["technologies"]

        print()
        print("=" * 60)
        print("STAGE 3.2 - TECHNOLOGY FREQUENCY REPORT")
        print("=" * 60)

        print(
            f"Jobs considered        : {total_jobs}"
        )

        print(
            f"Jobs with technologies : {analyzed_jobs}"
        )

        print()

        if not technologies:

            print(
                "No normalized technologies found."
            )

            print("=" * 60)

            return

        print(
            f"{'Technology':<25}"
            f"{'Jobs':>10}"
            f"{'Frequency':>15}"
        )

        print("-" * 60)

        for technology, count in technologies.most_common():

            percentage = (
                count / analyzed_jobs
            ) * 100 if analyzed_jobs else 0

            print(
                f"{technology:<25}"
                f"{count:>10}"
                f"{percentage:>14.1f}%"
            )

        print("=" * 60)