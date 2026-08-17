from __future__ import annotations

import re
from typing import Any

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)


class GupyAnalyzer:
    """
    Analyzer specifically for public Gupy job pages.

    Gupy public structure:

        Title

        Publicada em <date>

        Inscrições abertas até <date>

        Tipo de vaga: <contract>

        Modelo de trabalho: <model>

        DESCRIÇÃO DA VAGA

        ...

        RESPONSABILIDADES E ATRIBUIÇÕES

        ...

        REQUISITOS E QUALIFICAÇÕES

        ...

        INFORMAÇÕES ADICIONAIS

        ...

        ETAPAS DO PROCESSO

        ...

        BEM-VINDO À CRESOL
    """

    # =====================================================
    # Main
    # =====================================================

    async def analyze(
        self,
        page: Page,
        application_url: str,
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        fallback = fallback or {}

        # -------------------------------------------------
        # Convert Gupy application URL to public job URL
        # -------------------------------------------------

        job_url = self.convert_to_job_url(
            application_url
        )

        # -------------------------------------------------
        # Open public Gupy job page
        # -------------------------------------------------

        try:
            await page.goto(
                job_url,
                wait_until="domcontentloaded",
            )

        except PlaywrightTimeoutError:
            pass

        # -------------------------------------------------
        # Wait for content
        # -------------------------------------------------

        await self.wait_for_content(page)

        # -------------------------------------------------
        # Extract page text
        # -------------------------------------------------

        lines = await self.get_lines(page)

        # -------------------------------------------------
        # Page state
        # -------------------------------------------------

        if self.is_page_not_found(lines):

            return self.empty_result(
                application_url=job_url,
                job_status="CLOSED",
                page_not_found=True,
            )

        closed = self.is_job_closed(lines)

        # -------------------------------------------------
        # Header
        # -------------------------------------------------

        header = self.extract_header(lines)

        # -------------------------------------------------
        # Fallback
        #
        # Gupy may not expose company/location clearly.
        # -------------------------------------------------

        for field in (
            "title",
            "company",
            "location",
        ):

            if not header.get(field):

                header[field] = (
                    fallback.get(field)
                    or ""
                )

        # -------------------------------------------------
        # Description
        # -------------------------------------------------

        description = self.extract_section_text(
            lines,
            "Descrição da vaga",
        )

        # -------------------------------------------------
        # Responsibilities
        # -------------------------------------------------

        responsibilities = (
            self.extract_section_list(
                lines,
                "Responsabilidades e atribuições",
            )
        )

        # -------------------------------------------------
        # Requirements
        # -------------------------------------------------

        requirements = (
            self.extract_section_list(
                lines,
                "Requisitos e qualificações",
            )
        )

        # -------------------------------------------------
        # Benefits
        # -------------------------------------------------

        benefits = (
            self.extract_section_list(
                lines,
                "Informações adicionais",
            )
        )

        # -------------------------------------------------
        # Technologies
        # -------------------------------------------------

        technologies = (
            self.extract_technologies(
                lines
            )
        )

        # -------------------------------------------------
        # Level
        # -------------------------------------------------

        level = self.detect_level(
            header.get("title", ""),
            text="\n".join(lines),
        )

        # -------------------------------------------------
        # Final
        # -------------------------------------------------

        return {
            "page_not_found": False,

            "published_date": (
                header.get(
                    "published_date",
                    "",
                )
            ),

            "title": (
                header.get(
                    "title",
                    "",
                )
            ),

            "company": (
                header.get(
                    "company",
                    "",
                )
            ),

            "location": (
                header.get(
                    "location",
                    "",
                )
            ),

            "remote": (
                header.get(
                    "remote",
                    False,
                )
            ),

            "level": level,

            "contract": (
                header.get(
                    "contract",
                    "",
                )
            ),

            "job_source": "gupy",

            "application_url": job_url,

            "application_source": "gupy",

            "description": description,

            "responsibilities": responsibilities,

            "technologies": technologies,

            "requirements": requirements,

            "differentials": [],

            "benefits": benefits,

            "job_status": (
                "CLOSED"
                if closed
                else "NEW"
            ),
        }

    # =====================================================
    # URL
    # =====================================================

    @staticmethod
    def convert_to_job_url(
        application_url: str,
    ) -> str:

        if not application_url:
            return application_url

        # -------------------------------------------------
        # Example:
        #
        # https://cresolcarreiras.gupy.io/
        # candidates/jobs/11843837/apply
        # ?jobBoardSource=gupy_public_page
        #
        # becomes:
        #
        # https://cresolcarreiras.gupy.io/jobs/11843837
        # -------------------------------------------------

        match = re.search(
            r"^(https?://[^/]+)"
            r"/candidates/jobs/(\d+)",
            application_url,
            flags=re.IGNORECASE,
        )

        if match:

            domain = match.group(1)
            job_id = match.group(2)

            return (
                f"{domain}/jobs/{job_id}"
            )

        # -------------------------------------------------
        # Already public Gupy URL
        # -------------------------------------------------

        return application_url.split("?")[0]

    # =====================================================
    # Playwright
    # =====================================================

    async def wait_for_content(
        self,
        page: Page,
    ) -> None:

        try:

            await page.wait_for_load_state(
                "domcontentloaded"
            )

        except PlaywrightTimeoutError:

            pass

        try:

            await page.locator(
                "body"
            ).wait_for(
                state="attached",
                timeout=10000,
            )

        except PlaywrightTimeoutError:

            pass

        # -------------------------------------------------
        # Give Gupy's client-side rendering a small window
        # -------------------------------------------------

        try:

            await page.wait_for_timeout(
                1000
            )

        except Exception:

            pass

    async def get_lines(
        self,
        page: Page,
    ) -> list[str]:

        body = page.locator("body")

        text = await body.inner_text()

        lines = []

        for raw_line in text.splitlines():

            line = self.clean_line(
                raw_line
            )

            if not line:
                continue

            lines.append(line)

        return lines

    # =====================================================
    # Header
    # =====================================================

    def extract_header(
        self,
        lines: list[str],
    ) -> dict[str, Any]:

        result = {
            "published_date": "",
            "title": "",
            "company": "",
            "location": "",
            "remote": False,
            "level": "",
            "contract": "",
        }

        # -------------------------------------------------
        # Title
        #
        # Gupy public page normally has the job title
        # near the beginning of the page.
        #
        # Example:
        #
        # Analista de Testes | Sistemas 4 | ...
        # -------------------------------------------------

        section_index = self.find_heading(
            lines,
            "Descrição da vaga",
        )

        search_end = (
            section_index
            if section_index is not None
            else min(
                len(lines),
                30,
            )
        )

        for index in range(
            0,
            search_end,
        ):

            line = lines[index]

            if self.is_metadata_line(
                line
            ):
                continue

            if self.normalize(line) in {
                self.normalize(
                    "Pular para o conteúdo principal"
                ),
                self.normalize(
                    "Ir para a página da empresa"
                ),
                self.normalize(
                    "Candidatar-se"
                ),
                self.normalize(
                    "Copiar link"
                ),
            }:
                continue

            if self.normalize(line).startswith(
                "publicada em"
            ):
                continue

            if self.normalize(line).startswith(
                "inscrições abertas"
            ):
                continue

            # Avoid generic navigation text.

            if len(line) < 4:
                continue

            result["title"] = line

            break

        # -------------------------------------------------
        # Published date
        #
        # Publicada em 28 de julho de 2026
        # -------------------------------------------------

        for line in lines[:30]:

            match = re.match(
                r"^Publicada\s+em\s+(.+)$",
                line,
                flags=re.IGNORECASE,
            )

            if match:

                result["published_date"] = (
                    match.group(1).strip()
                )

                break

        # -------------------------------------------------
        # Contract
        #
        # Tipo de vaga: Efetivo
        # Tipo de vaga: EfetivoEfetivo
        # -------------------------------------------------

        for line in lines[:40]:

            match = re.match(
                r"^Tipo\s+de\s+vaga\s*:\s*(.+)$",
                line,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            result["contract"] = (
                self.clean_gupy_duplicate(
                    match.group(1)
                )
            )

            break

        # -------------------------------------------------
        # Work model
        #
        # Modelo de trabalho: Remoto
        # Modelo de trabalho: RemotoRemoto
        # -------------------------------------------------

        for line in lines[:40]:

            match = re.match(
                r"^Modelo\s+de\s+trabalho\s*:\s*(.+)$",
                line,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            model = self.clean_gupy_duplicate(
                match.group(1)
            )

            normalized_model = self.normalize(
                model
            )

            if any(
                value in normalized_model
                for value in (
                    "remoto",
                    "remote",
                    "home office",
                    "teletrabalho",
                )
            ):

                result["remote"] = True

            break

        # -------------------------------------------------
        # Location
        # -------------------------------------------------

        location_patterns = (
            r"^Local\s*:\s*(.+)$",
            r"^Localização\s*:\s*(.+)$",
            r"^Localizacao\s*:\s*(.+)$",
            r"^Cidade\s*:\s*(.+)$",
            r"^Location\s*:\s*(.+)$",
            r"^Local de trabalho\s*:\s*(.+)$",
        )

        for line in lines[:50]:

            for pattern in location_patterns:

                match = re.match(
                    pattern,
                    line,
                    flags=re.IGNORECASE,
                )

                if match:

                    result["location"] = (
                        self.clean_gupy_duplicate(
                            match.group(1)
                        )
                    )

                    return result

        return result

    # =====================================================
    # Description
    # =====================================================

    def extract_section_text(
        self,
        lines: list[str],
        heading: str,
    ) -> str:

        start = self.find_heading(
            lines,
            heading,
        )

        if start is None:
            return ""

        end = self.find_next_section(
            lines,
            start + 1,
        )

        section_lines = lines[
            start + 1:end
        ]

        cleaned = []

        for line in section_lines:

            if self.is_separator(line):
                continue

            cleaned.append(line)

        return "\n".join(
            cleaned
        ).strip()

    # =====================================================
    # Lists / sections
    # =====================================================

    def extract_section_list(
        self,
        lines: list[str],
        heading: str,
    ) -> list[str]:

        start = self.find_heading(
            lines,
            heading,
        )

        if start is None:
            return []

        end = self.find_next_section(
            lines,
            start + 1,
        )

        result = []

        for line in lines[
            start + 1:end
        ]:

            if self.is_separator(line):
                continue

            cleaned = self.clean_bullet(
                line
            )

            if not cleaned:
                continue

            # Ignore obvious navigation elements.

            normalized = self.normalize(
                cleaned
            )

            if normalized in {
                "candidatar-se",
                "copiar link",
                "entrar",
                "website",
                "linkedin",
                "facebook",
                "instagram",
                "glassdoor",
            }:
                continue

            result.append(cleaned)

        return self.unique(result)

    # =====================================================
    # Section detection
    # =====================================================

    def find_heading(
        self,
        lines: list[str],
        heading: str,
    ) -> int | None:

        target = self.normalize(
            heading
        )

        for index, line in enumerate(lines):

            if (
                self.normalize(line)
                == target
            ):

                return index

        return None

    def find_next_section(
        self,
        lines: list[str],
        start: int,
    ) -> int:

        section_headings = {
            self.normalize(
                "Descrição da vaga"
            ),

            self.normalize(
                "Responsabilidades e atribuições"
            ),

            self.normalize(
                "Requisitos e qualificações"
            ),

            self.normalize(
                "Informações adicionais"
            ),

            # -------------------------------------------------
            # Important:
            # These are also boundaries in the actual
            # Gupy page captured from Cresol.
            # -------------------------------------------------

            self.normalize(
                "Etapas do processo"
            ),

            self.normalize(
                "Bem-vindo à Cresol"
            ),

            self.normalize(
                "Saiba mais sobre a Cresol nas redes sociais"
            ),
        }

        for index in range(
            start,
            len(lines),
        ):

            normalized = self.normalize(
                lines[index]
            )

            if normalized in section_headings:

                return index

        return len(lines)

    # =====================================================
    # Technologies
    # =====================================================

    def extract_technologies(
        self,
        lines: list[str],
    ) -> list[str]:

        known = (
            "Cypress",
            "Playwright",
            "Selenium",
            "Robot Framework",
            "Appium",
            "Postman",
            "Jira",
            "Confluence",
            "Zephyr",
            "Java",
            "Python",
            "JavaScript",
            "TypeScript",
            "SQL",
            "SQL Server",
            "MySQL",
            "PostgreSQL",
            "Oracle",
            "MongoDB",
            "Docker",
            "Kubernetes",
            "AWS",
            "Azure",
            "GCP",
            "Git",
            "GitHub",
            "GitLab",
            "Jenkins",
            "CI/CD",
            "REST",
            "GraphQL",
            "API",
            "REST API",
        )

        text = " ".join(lines)

        result = []

        for technology in known:

            pattern = (
                r"(?<!\w)"
                + re.escape(technology)
                + r"(?!\w)"
            )

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                result.append(
                    technology
                )

        return self.unique(
            result
        )

    # =====================================================
    # Level
    # =====================================================

    def detect_level(
        self,
        title: str,
        text: str = "",
    ) -> str:

        # -------------------------------------------------
        # First check title.
        # -------------------------------------------------

        normalized_title = self.normalize(
            title
        )

        # Senior

        senior_patterns = (
            r"\bsenior\b",
            r"\bsênior\b",
            r"\bsr\.?\b",
            r"\blead\b",
            r"\bprincipal\b",
            r"\bstaff\b",
            r"\bespecialista\b",
            r"\bespecialist\b",
        )

        for pattern in senior_patterns:

            if re.search(
                pattern,
                normalized_title,
            ):

                return "Senior"

        # Mid

        mid_patterns = (
            r"\bpleno\b",
            r"\bmid\b",
            r"\bmid-level\b",
            r"\bmidlevel\b",
        )

        for pattern in mid_patterns:

            if re.search(
                pattern,
                normalized_title,
            ):

                return "Mid"

        # Junior

        junior_patterns = (
            r"\bjunior\b",
            r"\bjúnior\b",
            r"\bjr\.?\b",
            r"\btrainee\b",
            r"\bintern\b",
            r"\bestagiári[oa]\b",
        )

        for pattern in junior_patterns:

            if re.search(
                pattern,
                normalized_title,
            ):

                return "Junior"

        # -------------------------------------------------
        # Then check the complete text.
        # -------------------------------------------------

        normalized_text = self.normalize(
            text
        )

        for pattern in senior_patterns:

            if re.search(
                pattern,
                normalized_text,
            ):

                return "Senior"

        for pattern in mid_patterns:

            if re.search(
                pattern,
                normalized_text,
            ):

                return "Mid"

        for pattern in junior_patterns:

            if re.search(
                pattern,
                normalized_text,
            ):

                return "Junior"

        return ""

    # =====================================================
    # Page state
    # =====================================================

    def is_page_not_found(
        self,
        lines: list[str],
    ) -> bool:

        text = self.normalize(
            " ".join(lines)
        )

        markers = (
            "page not found",
            "404",
            "página não encontrada",
            "pagina nao encontrada",
            "vaga não encontrada",
            "vaga nao encontrada",
        )

        return any(
            marker in text
            for marker in markers
        )

    def is_job_closed(
        self,
        lines: list[str],
    ) -> bool:

        text = self.normalize(
            " ".join(lines)
        )

        markers = (
            "vaga encerrada",
            "vaga fechada",
            "inscrições encerradas",
            "inscricoes encerradas",
            "não aceita mais candidaturas",
            "nao aceita mais candidaturas",
            "vaga não está mais disponível",
            "vaga nao esta mais disponivel",
            "candidaturas encerradas",
            "processo seletivo encerrado",
        )

        return any(
            marker in text
            for marker in markers
        )

    # =====================================================
    # Helpers
    # =====================================================

    @staticmethod
    def normalize(
        value: str,
    ) -> str:

        value = value.replace(
            "\xa0",
            " ",
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip().casefold()

    @staticmethod
    def clean_line(
        value: str,
    ) -> str:

        value = value.replace(
            "\xa0",
            " ",
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    @staticmethod
    def clean_bullet(
        value: str,
    ) -> str:

        value = value.strip()

        value = re.sub(
            r"^[\-*•●▪◦‣]\s*",
            "",
            value,
        )

        return value.strip()

    @staticmethod
    def is_separator(
        value: str,
    ) -> bool:

        return bool(
            re.fullmatch(
                r"[-_]{3,}",
                value.strip(),
            )
        )

    @staticmethod
    def clean_gupy_duplicate(
        value: str,
    ) -> str:

        value = re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

        if not value:
            return ""

        # -------------------------------------------------
        # Examples:
        #
        # EfetivoEfetivo -> Efetivo
        # RemotoRemoto   -> Remoto
        # -------------------------------------------------

        if len(value) % 2 == 0:

            half = len(value) // 2

            first = value[:half]
            second = value[half:]

            if (
                first.casefold()
                == second.casefold()
            ):

                return first.strip()

        return value

    @staticmethod
    def unique(
        values: list[str],
    ) -> list[str]:

        result = []

        seen = set()

        for value in values:

            value = str(
                value
            ).strip()

            if not value:
                continue

            key = value.casefold()

            if key in seen:
                continue

            seen.add(key)

            result.append(
                value
            )

        return result

    @staticmethod
    def is_metadata_line(
        value: str,
    ) -> bool:

        normalized = value.casefold()

        return (
            normalized.startswith(
                "publicada em "
            )
            or normalized.startswith(
                "inscrições abertas"
            )
            or normalized.startswith(
                "inscricoes abertas"
            )
            or normalized.startswith(
                "tipo de vaga:"
            )
            or normalized.startswith(
                "modelo de trabalho:"
            )
        )

    # =====================================================
    # Empty result
    # =====================================================

    @staticmethod
    def empty_result(
        application_url: str,
        job_status: str = "CLOSED",
        page_not_found: bool = True,
    ) -> dict[str, Any]:

        return {
            "page_not_found": page_not_found,

            "published_date": "",

            "title": "",

            "company": "",

            "location": "",

            "remote": False,

            "level": "",

            "contract": "",

            "job_source": "gupy",

            "application_url": (
                application_url
            ),

            "application_source": "gupy",

            "description": "",

            "responsibilities": [],

            "technologies": [],

            "requirements": [],

            "differentials": [],

            "benefits": [],

            "job_status": job_status,
        }


if __name__ == "__main__":
    pass