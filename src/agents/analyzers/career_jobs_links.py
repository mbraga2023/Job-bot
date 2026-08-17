# agents/analyzers/career_jobs_links.py

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)
class CareerJobsLinksAnalyzer:
    """
    Generic career-page analyzer.

    The analyzer intentionally does not depend on:
        - specific CSS selectors
        - specific career platforms
        - specific HTML structures
        - Portuguese-only labels

    The primary extraction source is visible page text.

    Extraction strategy:

        page
          ↓
        visible text
          ↓
        normalized lines
          ↓
        field / section detection
          ↓
        structured job data
    """

    # =====================================================
    # Field labels
    # =====================================================

    FIELD_LABELS = {

        "title": (
            "job title",
            "job name",
            "position",
            "position title",
            "title",
            "cargo",
            "título",
            "titulo",
            "nome da vaga",
            "vaga",
        ),

        "company": (
            "company",
            "company name",
            "employer",
            "organization",
            "organisation",
            "empresa",
            "nome da empresa",
        ),

        "location": (
            "location",
            "job location",
            "work location",
            "localização",
            "localizacao",
            "local",
            "cidade",
            "city",
            "state",
            "state/province",
            "province",
            "estado",
        ),

        "published_date": (
            "posting date",
            "posted date",
            "posting start date",
            "date posted",
            "published date",
            "published",
            "posted",
            "publication date",
            "data de publicação",
            "data de publicacao",
            "publicado",
            "publicada",
            "data de postagem",
            "data de início",
            "data de inicio",
        ),

        "level": (
            "level",
            "job level",
            "seniority",
            "seniority level",
            "career level",
            "job seniority",
            "nível",
            "nivel",
            "senioridade",
        ),

        "contract": (
            "contract",
            "contract type",
            "employment type",
            "employment",
            "job type",
            "tipo de contrato",
            "contrato",
            "tipo de emprego",
        ),
    }

    # =====================================================
    # Level
    # =====================================================

    LEVEL_SENIOR = (
        "senior",
        "sênior",
        "sr",
        "sr.",
        "lead",
        "principal",
        "staff",
        "expert",
        "specialist",
    )

    LEVEL_MID = (
        "mid",
        "mid-level",
        "mid level",
        "midlevel",
        "middle",
        "pleno",
    )

    LEVEL_JUNIOR = (
        "junior",
        "júnior",
        "jr",
        "jr.",
        "entry level",
        "entry-level",
        "entrylevel",
        "trainee",
        "intern",
        "internship",
        "estagiário",
        "estagiaria",
        "estágio",
        "estagio",
    )

    # =====================================================
    # Experience ranges
    # =====================================================

    EXPERIENCE_LABELS = (
        "experience",
        "years of experience",
        "required experience",
        "minimum experience",
        "professional experience",
        "experiência",
        "anos de experiência",
        "anos de experiencia",
        "experiência profissional",
        "experiencia profissional",
    )

    # =====================================================
    # Remote
    # =====================================================

    REMOTE_TRUE = {
        "remote",
        "remoto",
        "remota",
        "work from home",
        "home office",
        "telecommute",
        "telecommuting",
        "100% remote",
        "fully remote",
        "híbrido",
        "hibrido",
        "hybrid",
    }

    REMOTE_FALSE = {
        "on-site",
        "onsite",
        "on site",
        "presencial",
        "in-office",
        "in office",
    }

    # =====================================================
    # Page not found
    # =====================================================

    PAGE_NOT_FOUND_MARKERS = (
        "page not found",
        "404",
        "not found",
        "page doesn't exist",
        "page does not exist",
        "página não encontrada",
        "pagina nao encontrada",
        "página inexistente",
        "pagina inexistente",
        "vaga não encontrada",
        "vaga nao encontrada",
        "vaga não existe",
        "vaga nao existe",
        "job not found",
        "job does not exist",
        "job doesn't exist",
        "position not found",
    )

    # =====================================================
    # Closed
    # =====================================================

    CLOSED_MARKERS = (
        "vaga encerrada",
        "vaga fechada",
        "vaga não está mais disponível",
        "vaga nao esta mais disponivel",
        "não aceita mais candidaturas",
        "nao aceita mais candidaturas",
        "não está mais aceitando candidaturas",
        "nao esta mais aceitando candidaturas",

        "job is closed",
        "job closed",
        "position is closed",
        "position closed",
        "no longer available",
        "no longer accepting applications",
        "applications are closed",
        "this position has been filled",
        "position has been filled",
        "job has been filled",
        "this job is no longer available",
    )

    # =====================================================
    # Description sections
    # =====================================================

    DESCRIPTION_SECTIONS = (
        "job description",
        "job details",
        "about the job",
        "about this job",
        "about the role",
        "role description",

        "descrição da vaga",
        "descricao da vaga",
        "descrição",
        "descricao",
        "sobre a vaga",
        "sobre o cargo",
        "sobre a posição",
        "sobre a posicao",
    )

    # =====================================================
    # Responsibility sections
    # =====================================================

    RESPONSIBILITY_SECTIONS = (
        "responsibilities",
        "key responsibilities",
        "main responsibilities",
        "responsibility",
        "what you'll do",
        "what you will do",
        "what you'll be doing",
        "what you will be doing",

        "responsabilidades",
        "principais responsabilidades",
        "atividades",
        "atribuições",
        "atribuicoes",
    )

    # =====================================================
    # Requirement sections
    # =====================================================

    REQUIREMENT_SECTIONS = (
        "requirements",
        "required qualifications",
        "qualifications",
        "basic qualifications",
        "preferred qualifications",
        "skills and qualifications",
        "what we're looking for",
        "what we are looking for",
        "you should have",

        "requisitos",
        "qualificações",
        "qualificacoes",
        "requisitos obrigatórios",
        "requisitos obrigatorios",
        "perfil",
    )

    # =====================================================
    # Technology sections
    # =====================================================

    TECHNOLOGY_SECTIONS = (
        "technologies",
        "technology",
        "technical skills",
        "technical requirements",
        "technical qualifications",
        "skills",
        "key skills",
        "mandatory skills",
        "required skills",
        "must have skills",

        "tecnologias",
        "tecnologia",
        "habilidades técnicas",
        "habilidades tecnicas",
        "competências técnicas",
        "competencias tecnicas",
        "skills obrigatórias",
        "skills obrigatorias",
    )

    # =====================================================
    # Differential sections
    # =====================================================

    DIFFERENTIAL_SECTIONS = (
        "differentials",
        "differential",
        "preferred skills",
        "nice to have",
        "good to have",
        "desired skills",

        "diferenciais",
        "diferencial",
        "desejável",
        "desejavel",
    )

    # =====================================================
    # Benefits
    # =====================================================

    BENEFIT_SECTIONS = (
        "benefits",
        "employee benefits",
        "what we offer",
        "we offer",
        "perks",
        "compensation and benefits",

        "benefícios",
        "beneficios",
        "o que oferecemos",
        "vantagens",
    )

    # =====================================================
    # Application
    # =====================================================

    APPLY_TEXT_PATTERNS = (
        r"\bapply\b",
        r"\bapply now\b",
        r"\bapply here\b",
        r"\bapply for this job\b",
        r"\bsubmit application\b",
        r"\bsubmit your application\b",
        r"\bstart application\b",
        r"\bapplication\b",

        r"\bcandidatar\b",
        r"\bcandidate-se\b",
        r"\bcandidatar-se\b",
        r"\bcandidatura\b",
        r"\binscreva-se\b",
        r"\baplicar\b",
    )

    # =====================================================
    # All sections
    # =====================================================

    ALL_SECTION_LABELS = (
        DESCRIPTION_SECTIONS
        + RESPONSIBILITY_SECTIONS
        + REQUIREMENT_SECTIONS
        + TECHNOLOGY_SECTIONS
        + DIFFERENTIAL_SECTIONS
        + BENEFIT_SECTIONS
    )

    # =====================================================
    # Analyze
    # =====================================================

    async def analyze(
        self,
        page: Page,
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        fallback = fallback or {}

        await self.wait_for_content(
            page
        )

        lines = await self.get_lines(
            page
        )

        # -------------------------------------------------
        # Page not found
        # -------------------------------------------------

        if self.is_page_not_found(
            lines
        ):

            return self.empty_result(
                page_not_found=True,
                job_status="CLOSED",
            )

        # -------------------------------------------------
        # Closed
        # -------------------------------------------------

        closed = self.is_job_closed(
            lines
        )

        # -------------------------------------------------
        # Header
        # -------------------------------------------------

        header = await self.extract_header(
            page,
            lines,
        )

        # -------------------------------------------------
        # Apply fallback data from career_jobs
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
        # Application URL
        # -------------------------------------------------

        application_url = (
    await self.get_application_url(
        page
    )
)

        if application_url:

            application_url = urljoin(
                page.url,
                application_url,
            )

            if self.is_gupy_url(application_url):

                from agents.analyzers.gupy import GupyAnalyzer

                gupy_analyzer = GupyAnalyzer()

                return await gupy_analyzer.analyze(
                    page=page,
                    application_url=application_url,
                    fallback=fallback,
                )

        # -------------------------------------------------
        # Description
        # -------------------------------------------------

        description = (
            self.extract_description(
                lines
            )
        )

        if not description:

            description = (
                self.extract_description_fallback(
                    lines
                )
            )

        # -------------------------------------------------
        # Responsibilities
        # -------------------------------------------------

        responsibilities = (
            self.extract_section_group(
                lines,
                self.RESPONSIBILITY_SECTIONS,
            )
        )

        # -------------------------------------------------
        # Requirements
        # -------------------------------------------------

        requirements = (
            self.extract_section_group(
                lines,
                self.REQUIREMENT_SECTIONS,
            )
        )

        # -------------------------------------------------
        # Technologies
        # -------------------------------------------------

        technologies = (
            self.extract_section_group(
                lines,
                self.TECHNOLOGY_SECTIONS,
            )
        )

        # -------------------------------------------------
        # Differentials
        # -------------------------------------------------

        differentials = (
            self.extract_section_group(
                lines,
                self.DIFFERENTIAL_SECTIONS,
            )
        )

        # -------------------------------------------------
        # Benefits
        # -------------------------------------------------

        benefits = (
            self.extract_section_group(
                lines,
                self.BENEFIT_SECTIONS,
            )
        )

        # -------------------------------------------------
        # Inline skills
        # -------------------------------------------------

        inline_skills = (
            self.extract_inline_skills(
                lines
            )
        )

        for skill in inline_skills:

            if skill not in technologies:

                technologies.append(
                    skill
                )

        # -------------------------------------------------
        # Experience
        # -------------------------------------------------

        experience = (
            self.extract_experience(
                lines
            )
        )

        if experience:

            requirements = self.append_unique(
                requirements,
                f"Experience: {experience}",
            )

        # -------------------------------------------------
        # LEVEL
        #
        # Important:
        #
        # We determine level using multiple signals:
        #
        # 1. Explicit Level field
        # 2. Job title
        # 3. Header text
        # 4. Experience range
        #
        # Priority is deliberate.
        # -------------------------------------------------

        level = self.detect_level(
            lines=lines,
            title=header.get(
                "title",
                "",
            ),
            explicit_level=header.get(
                "level",
                "",
            ),
            experience=experience,
        )

        header["level"] = level

        # -------------------------------------------------
        # Remote
        # -------------------------------------------------

        remote = header.get(
            "remote",
            False,
        )

        # -------------------------------------------------
        # Job source
        # -------------------------------------------------

        job_source = (
            self.detect_job_source(
                page,
                lines,
            )
        )

        # -------------------------------------------------
        # Application source
        # -------------------------------------------------

        application_source = (
            self.detect_application_source(
                application_url,
                page.url,
            )
        )

        # -------------------------------------------------
        # Final status
        # -------------------------------------------------

        if closed:

            job_status = "CLOSED"

        else:

            job_status = "NEW"

        # -------------------------------------------------
        # Final result
        # -------------------------------------------------

        return {

            "page_not_found": False,

            "published_date": header.get(
                "published_date",
                "",
            ),

            "title": header.get(
                "title",
                "",
            ),

            "company": header.get(
                "company",
                "",
            ),

            "location": header.get(
                "location",
                "",
            ),

            "remote": remote,

            "level": level,

            "contract": header.get(
                "contract",
                "",
            ),

            "job_source": job_source,

            "application_url": (
                application_url
                or page.url
            ),

            "application_source": (
                application_source
            ),

            "description": description,

            "technologies": (
                self.unique_items(
                    technologies
                )
            ),

            "requirements": (
                self.unique_items(
                    requirements
                )
            ),

            "differentials": (
                self.unique_items(
                    differentials
                )
            ),

            "benefits": (
                self.unique_items(
                    benefits
                )
            ),

            "job_status": job_status,
        }

    # =====================================================
    # Empty
    # =====================================================

    def empty_result(
        self,
        page_not_found: bool = False,
        job_status: str = "CLOSED",
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

            "job_source": "",

            "application_url": "",

            "application_source": "",

            "description": "",

            "technologies": [],

            "requirements": [],

            "differentials": [],

            "benefits": [],

            "job_status": job_status,
        }

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
                timeout=5000,
            )

        except PlaywrightTimeoutError:

            pass

        try:

            await page.wait_for_load_state(
                "networkidle",
                timeout=5000,
            )

        except PlaywrightTimeoutError:

            pass

    # =====================================================
    # Visible text
    # =====================================================

    async def get_lines(
        self,
        page: Page,
    ) -> list[str]:

        body = page.locator(
            "body"
        )

        await body.wait_for(
            state="attached"
        )

        text = await body.inner_text()

        lines = []

        for raw_line in text.splitlines():

            line = self.clean_line(
                raw_line
            )

            if line:

                lines.append(
                    line
                )

        if os.getenv(
            "ANALYZER_DEBUG"
        ) == "1":

            print(
                f"URL: {page.url}"
            )

            print(
                f"Text size: {len(text)}"
            )

            for index, line in enumerate(
                lines
            ):

                print(
                    f"{index}: {line!r}"
                )

        return lines

    # =====================================================
    # Application URL
    # =====================================================

    async def get_application_url(
        self,
        page: Page,
    ) -> str:

        try:

            candidates = page.locator(
                "a, button"
            )

            count = await candidates.count()

            for index in range(count):

                candidate = candidates.nth(
                    index
                )

                try:

                    if not await candidate.is_visible():
                        continue

                    text = self.clean_line(
                        await candidate.inner_text()
                    )

                    if not text:
                        continue

                    if not self.is_apply_text(
                        text
                    ):
                        continue

                    href = await candidate.get_attribute(
                        "href"
                    )

                    if href:

                        return href

                except Exception:

                    continue

        except Exception:

            pass

        # -------------------------------------------------
        # Text fallback
        # -------------------------------------------------

        for pattern in self.APPLY_TEXT_PATTERNS:

            try:

                locator = page.get_by_text(
                    re.compile(
                        pattern,
                        re.IGNORECASE,
                    )
                )

                count = await locator.count()

                for index in range(count):

                    candidate = locator.nth(
                        index
                    )

                    try:

                        if not await candidate.is_visible():
                            continue

                        href = await candidate.get_attribute(
                            "href"
                        )

                        if href:

                            return href

                        parent = candidate.locator(
                            "xpath=ancestor::a[1]"
                        )

                        if await parent.count():

                            href = await parent.first.get_attribute(
                                "href"
                            )

                            if href:

                                return href

                    except Exception:

                        continue

            except Exception:

                continue

        return ""

    # =====================================================
    # Header
    # =====================================================

    async def extract_header(
        self,
        page: Page,
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
        # Normal labeled fields
        # -------------------------------------------------

        for field, labels in self.FIELD_LABELS.items():

            value = self.find_labeled_value(
                lines,
                labels,
            )

            if value:

                result[field] = value

        # -------------------------------------------------
        # City + State
        # -------------------------------------------------

        city = self.find_labeled_value(
            lines,
            (
                "city",
                "cidade",
            ),
        )

        state = self.find_labeled_value(
            lines,
            (
                "state",
                "state/province",
                "province",
                "estado",
            ),
        )

        if city and state:

            result["location"] = (
                f"{city}, {state}"
            )

        elif city:

            result["location"] = city

        elif state and not result["location"]:

            result["location"] = state

        # -------------------------------------------------
        # Remote
        # -------------------------------------------------

        remote_value = self.find_labeled_value(
            lines,
            (
                "work model",
                "work mode",
                "working model",
                "work arrangement",
                "workplace type",
                "remote",
                "location type",
                "modalidade",
                "modelo de trabalho",
                "regime",
            ),
        )

        if remote_value:

            result["remote"] = (
                self.is_remote_value(
                    remote_value
                )
            )

        else:

            # Only inspect the header area.
            for line in lines[:80]:

                normalized = self.normalize(
                    line
                )

                if normalized in {
                    self.normalize(item)
                    for item in self.REMOTE_TRUE
                }:

                    result["remote"] = True

                    break

                if normalized in {
                    self.normalize(item)
                    for item in self.REMOTE_FALSE
                }:

                    result["remote"] = False

                    break

        # -------------------------------------------------
        # Title fallback
        # -------------------------------------------------

        if not result["title"]:

            result["title"] = (
                self.find_title_fallback(
                    lines
                )
            )

        # -------------------------------------------------
        # Company fallback
        # -------------------------------------------------

        if not result["company"]:

            result["company"] = (
                await self.find_company_fallback(
                    page,
                    lines,
                )
            )

        # -------------------------------------------------
        # Level is deliberately NOT finalized here.
        #
        # detect_level() runs after experience extraction.
        # -------------------------------------------------

        return result

    # =====================================================
    # Labeled value
    # =====================================================

    def find_labeled_value(
        self,
        lines: list[str],
        labels: tuple[str, ...],
    ) -> str:

        normalized_labels = {
            self.normalize(label)
            for label in labels
        }

        for index, line in enumerate(
            lines
        ):

            normalized_line = self.normalize(
                line
            )

            # -------------------------------------------------
            # Inline
            #
            # Job Title: QA Engineer
            # -------------------------------------------------

            for label in normalized_labels:

                pattern = (
                    r"^"
                    + re.escape(label)
                    + r"\s*:\s*(.+)$"
                )

                match = re.match(
                    pattern,
                    normalized_line,
                    flags=re.IGNORECASE,
                )

                if match:

                    value = re.split(
                        r":",
                        line,
                        maxsplit=1,
                    )[1].strip()

                    return self.clean_value(
                        value
                    )

            # -------------------------------------------------
            # Separate lines
            #
            # Job Title:
            # QA Engineer
            # -------------------------------------------------

            if normalized_line in normalized_labels:

                if index + 1 < len(lines):

                    next_line = lines[
                        index + 1
                    ]

                    if not self.looks_like_label(
                        next_line
                    ):

                        return self.clean_value(
                            next_line
                        )

        return ""

    # =====================================================
    # Title fallback
    # =====================================================

    def find_title_fallback(
        self,
        lines: list[str],
    ) -> str:

        value = self.find_labeled_value(
            lines,
            (
                "job title",
                "position title",
                "position",
                "cargo",
            ),
        )

        if value:

            return value

        # -------------------------------------------------
        # Example:
        #
        # Job Description:
        # QA Engineer
        # -------------------------------------------------

        for index, line in enumerate(
            lines
        ):

            if self.is_section_label(
                line,
                self.DESCRIPTION_SECTIONS,
            ):

                if index + 1 < len(lines):

                    candidate = lines[
                        index + 1
                    ]

                    if not self.looks_like_label(
                        candidate
                    ):

                        return candidate

        return ""

    # =====================================================
    # Company fallback
    # =====================================================

    async def find_company_fallback(
        self,
        page: Page,
        lines: list[str],
    ) -> str:

        # -------------------------------------------------
        # og:site_name
        # -------------------------------------------------

        try:

            locator = page.locator(
                'meta[property="og:site_name"]'
            )

            if await locator.count():

                value = await locator.first.get_attribute(
                    "content"
                )

                if value:

                    return self.clean_company(
                        value
                    )

        except Exception:

            pass

        # -------------------------------------------------
        # author
        # -------------------------------------------------

        try:

            locator = page.locator(
                'meta[name="author"]'
            )

            if await locator.count():

                value = await locator.first.get_attribute(
                    "content"
                )

                if value:

                    return self.clean_company(
                        value
                    )

        except Exception:

            pass

        # -------------------------------------------------
        # Page title
        # -------------------------------------------------

        try:

            page_title = await page.title()

            company = (
                self.company_from_page_title(
                    page_title
                )
            )

            if company:

                return company

        except Exception:

            pass

        # -------------------------------------------------
        # Visible text
        # -------------------------------------------------

        for line in lines[:30]:

            company = (
                self.company_from_careers_text(
                    line
                )
            )

            if company:

                return company

        return ""

    # =====================================================
    # Company from page title
    # =====================================================

    def company_from_page_title(
        self,
        title: str,
    ) -> str:

        value = self.clean_line(
            title
        )

        if not value:

            return ""

        patterns = (
            r"^(.+?)\s+careers?$",
            r"^careers?\s*[-|–—]\s*(.+)$",
            r"^(.+?)\s+jobs?$",
            r"^jobs?\s*[-|–—]\s*(.+)$",
        )

        for pattern in patterns:

            match = re.match(
                pattern,
                value,
                flags=re.IGNORECASE,
            )

            if match:

                return self.clean_company(
                    match.group(1)
                )

        return ""

    # =====================================================
    # Company from visible text
    # =====================================================

    def company_from_careers_text(
        self,
        line: str,
    ) -> str:

        match = re.match(
            r"^(.+?)\s+careers?$",
            line,
            flags=re.IGNORECASE,
        )

        if match:

            return self.clean_company(
                match.group(1)
            )

        return ""

    # =====================================================
    # LEVEL DETECTION
    # =====================================================

    def detect_level(
        self,
        lines: list[str],
        title: str,
        explicit_level: str,
        experience: str,
    ) -> str:

        # -------------------------------------------------
        # Priority 1:
        # Explicit field
        #
        # Level: Senior
        # Seniority: Mid
        # -------------------------------------------------

        level = self.level_from_keyword(
            explicit_level
        )

        if level:

            return level

        # -------------------------------------------------
        # Priority 2:
        # Job title
        #
        # Senior QA Engineer
        # QA Engineer - Junior
        # QA Engineer (Mid-Level)
        # -------------------------------------------------

        level = self.level_from_title(
            title
        )

        if level:

            return level

        # -------------------------------------------------
        # Priority 3:
        # Experience
        #
        # 8-10 Years -> Senior
        # 6+ years   -> Senior
        # 3-5 Years  -> Mid
        # 1-2 Years  -> Junior
        # -------------------------------------------------

        level = self.level_from_experience(
            experience
        )

        if level:

            return level

        # -------------------------------------------------
        # Priority 4:
        # Search the first part of the page.
        #
        # IMPORTANT:
        #
        # We do NOT search the entire page blindly.
        #
        # This prevents text such as:
        #
        # "senior stakeholders"
        #
        # from incorrectly tagging the job Senior.
        # -------------------------------------------------

        level = self.level_from_header_text(
            lines
        )

        if level:

            return level

        return ""

    # =====================================================
    # Level from explicit keyword
    # =====================================================

    def level_from_keyword(
        self,
        value: str,
    ) -> str:

        if not value:

            return ""

        normalized = self.normalize(
            value
        )

        # Senior first because "senior"
        # is the strongest classification.
        if self.contains_level_keyword(
            normalized,
            self.LEVEL_SENIOR,
        ):

            return "Senior"

        if self.contains_level_keyword(
            normalized,
            self.LEVEL_MID,
        ):

            return "Mid"

        if self.contains_level_keyword(
            normalized,
            self.LEVEL_JUNIOR,
        ):

            return "Junior"

        return ""

    # =====================================================
    # Level from title
    # =====================================================

    def level_from_title(
        self,
        title: str,
    ) -> str:

        if not title:

            return ""

        normalized = self.normalize(
            title
        )

        # -------------------------------------------------
        # Senior
        # -------------------------------------------------

        if self.contains_level_keyword(
            normalized,
            self.LEVEL_SENIOR,
        ):

            return "Senior"

        # -------------------------------------------------
        # Mid
        # -------------------------------------------------

        if self.contains_level_keyword(
            normalized,
            self.LEVEL_MID,
        ):

            return "Mid"

        # -------------------------------------------------
        # Junior
        # -------------------------------------------------

        if self.contains_level_keyword(
            normalized,
            self.LEVEL_JUNIOR,
        ):

            return "Junior"

        return ""

    # =====================================================
    # Level from experience
    # =====================================================

    def level_from_experience(
        self,
        experience: str,
    ) -> str:

        if not experience:

            return ""

        normalized = self.normalize(
            experience
        )

        # -------------------------------------------------
        # Explicit senior wording
        # -------------------------------------------------

        if any(
            word in normalized
            for word in (
                "senior",
                "sênior",
            )
        ):

            return "Senior"

        # -------------------------------------------------
        # Explicit junior wording
        # -------------------------------------------------

        if any(
            word in normalized
            for word in (
                "junior",
                "júnior",
                "entry level",
                "entry-level",
                "trainee",
            )
        ):

            return "Junior"

        # -------------------------------------------------
        # Range:
        #
        # 8-10 years
        # 6-8 years
        # 5-7 years
        # -------------------------------------------------

        range_match = re.search(
            r"(\d+)\s*[-–]\s*(\d+)\s*(?:\+)?\s*(?:years?|anos?)",
            normalized,
            flags=re.IGNORECASE,
        )

        if range_match:

            minimum = int(
                range_match.group(1)
            )

            maximum = int(
                range_match.group(2)
            )

            return self.level_from_year_values(
                minimum,
                maximum,
            )

        # -------------------------------------------------
        # Plus:
        #
        # 6+ years
        # 5+ years
        # 3+ years
        # -------------------------------------------------

        plus_match = re.search(
            r"(\d+)\s*\+\s*(?:years?|anos?)",
            normalized,
            flags=re.IGNORECASE,
        )

        if plus_match:

            minimum = int(
                plus_match.group(1)
            )

            return self.level_from_year_values(
                minimum,
                None,
            )

        # -------------------------------------------------
        # "At least 5 years"
        # -------------------------------------------------

        at_least_match = re.search(
            r"(?:at least|minimum of|minimum)\s+(\d+)\s*(?:years?|anos?)",
            normalized,
            flags=re.IGNORECASE,
        )

        if at_least_match:

            minimum = int(
                at_least_match.group(1)
            )

            return self.level_from_year_values(
                minimum,
                None,
            )

        # -------------------------------------------------
        # Plain:
        #
        # 3 years experience
        # -------------------------------------------------

        plain_match = re.search(
            r"\b(\d+)\s*(?:years?|anos?)",
            normalized,
            flags=re.IGNORECASE,
        )

        if plain_match:

            years = int(
                plain_match.group(1)
            )

            return self.level_from_year_values(
                years,
                years,
            )

        return ""

    # =====================================================
    # Experience → level
    # =====================================================

    @staticmethod
    def level_from_year_values(
        minimum: int,
        maximum: int | None,
    ) -> str:

        # -------------------------------------------------
        # 0-2 years
        # -------------------------------------------------

        if minimum <= 2:

            return "Junior"

        # -------------------------------------------------
        # 2-5 years
        #
        # 3-5
        # 2-4
        # 3-4
        # -------------------------------------------------

        if minimum <= 4:

            return "Mid"

        # -------------------------------------------------
        # 5+ years
        # -------------------------------------------------

        return "Senior"

    # =====================================================
    # Level from header
    # =====================================================

    def level_from_header_text(
        self,
        lines: list[str],
    ) -> str:

        # -------------------------------------------------
        # Only inspect the first 80 lines.
        # -------------------------------------------------

        for line in lines[:80]:

            normalized = self.normalize(
                line
            )

            # Explicit level labels are stronger.
            if (
                normalized.startswith(
                    "level:"
                )
                or normalized.startswith(
                    "seniority:"
                )
                or normalized.startswith(
                    "job level:"
                )
            ):

                level = self.level_from_keyword(
                    normalized
                )

                if level:

                    return level

            # -------------------------------------------------
            # Do not classify generic paragraphs.
            #
            # Only inspect short lines where a level
            # is likely to represent the job.
            # -------------------------------------------------

            if len(normalized) > 100:

                continue

            if self.is_probable_job_header_line(
                normalized
            ):

                level = self.level_from_keyword(
                    normalized
                )

                if level:

                    return level

        return ""

    # =====================================================
    # Probable job header
    # =====================================================

    def is_probable_job_header_line(
        self,
        normalized: str,
    ) -> bool:

        header_markers = (
            "job title",
            "position",
            "role",
            "job",
            "career",
            "opening",
            "vacancy",
            "cargo",
            "vaga",
            "posição",
            "posicao",
        )

        return any(
            marker in normalized
            for marker in header_markers
        )

    # =====================================================
    # Keyword matcher
    # =====================================================

    def contains_level_keyword(
        self,
        text: str,
        keywords: tuple[str, ...],
    ) -> bool:

        for keyword in keywords:

            normalized_keyword = self.normalize(
                keyword
            )

            # -------------------------------------------------
            # Special handling for abbreviations.
            #
            # sr / sr.
            # jr / jr.
            # -------------------------------------------------

            if normalized_keyword in {
                "sr",
                "sr.",
                "jr",
                "jr.",
            }:

                pattern = (
                    r"\b"
                    + re.escape(
                        normalized_keyword.rstrip(".")
                    )
                    + r"\.?\b"
                )

            else:

                pattern = (
                    r"(?<!\w)"
                    + re.escape(
                        normalized_keyword
                    )
                    + r"(?!\w)"
                )

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                return True

        return False

    # =====================================================
    # Experience extraction
    # =====================================================

    def extract_experience(
        self,
        lines: list[str],
    ) -> str:

        # -------------------------------------------------
        # First: explicit Experience field
        # -------------------------------------------------

        value = self.find_labeled_value(
            lines,
            self.EXPERIENCE_LABELS,
        )

        if value:

            return value

        # -------------------------------------------------
        # Search all lines for:
        #
        # Experience: 8-10 Years
        #
        # but only accept a line explicitly talking about
        # experience.
        # -------------------------------------------------

        for line in lines:

            normalized = self.normalize(
                line
            )

            if "experience" not in normalized and \
               "experiência" not in normalized and \
               "experiencia" not in normalized:

                continue

            if re.search(
                r"\d+\s*(?:[-–]\s*\d+|\+)?\s*(?:years?|anos?)",
                normalized,
                flags=re.IGNORECASE,
            ):

                if ":" in line:

                    value = line.split(
                        ":",
                        1,
                    )[1].strip()

                    return self.clean_value(
                        value
                    )

                return self.clean_value(
                    line
                )

        return ""

    # =====================================================
    # Section extraction
    # =====================================================

    def extract_description(
        self,
        lines: list[str],
    ) -> str:

        start = self.find_section_index(
            lines,
            self.DESCRIPTION_SECTIONS,
        )

        if start == -1:

            return ""

        items = []

        for line in lines[
            start + 1:
        ]:

            if self.is_any_section_label(
                line
            ):

                break

            if self.looks_like_footer(
                line
            ):

                break

            if line == "•":

                continue

            items.append(
                line
            )

        return self.join_text(
            items
        )

    # =====================================================
    # Description fallback
    # =====================================================

    def extract_description_fallback(
        self,
        lines: list[str],
    ) -> str:

        start_index = -1

        for index, line in enumerate(
            lines[:100]
        ):

            normalized = self.normalize(
                line
            )

            if normalized in {
                self.normalize(item)
                for item in self.DESCRIPTION_SECTIONS
            }:

                start_index = index

                break

        if start_index == -1:

            return ""

        items = []

        for line in lines[
            start_index + 1:
        ]:

            if self.is_any_section_label(
                line
            ):

                break

            if self.looks_like_footer(
                line
            ):

                break

            items.append(
                line
            )

        return self.join_text(
            items
        )

    # =====================================================
    # Generic section
    # =====================================================

    def extract_section_group(
        self,
        lines: list[str],
        section_names: tuple[str, ...],
    ) -> list[str]:

        start = self.find_section_index(
            lines,
            section_names,
        )

        if start == -1:

            return []

        items = []

        for line in lines[
            start + 1:
        ]:

            if self.is_any_section_label(
                line
            ):

                break

            if self.looks_like_footer(
                line
            ):

                break

            value = self.clean_section_line(
                line
            )

            if value:

                items.append(
                    value
                )

        return self.unique_items(
            items
        )

    # =====================================================
    # Inline skills
    # =====================================================

    def extract_inline_skills(
        self,
        lines: list[str],
    ) -> list[str]:

        results = []

        labels = (
            "mandatory skills",
            "required skills",
            "must have skills",
            "key skills",
            "technical skills",
            "skills",
            "habilidades técnicas",
            "habilidades tecnicas",
            "competências técnicas",
            "competencias tecnicas",
            "tecnologias",
        )

        for line in lines:

            for label in labels:

                pattern = (
                    r"^"
                    + re.escape(label)
                    + r"\s*:\s*(.+)$"
                )

                match = re.match(
                    pattern,
                    self.normalize(line),
                    flags=re.IGNORECASE,
                )

                if not match:

                    continue

                if ":" not in line:

                    continue

                value = line.split(
                    ":",
                    1,
                )[1].strip()

                value = self.clean_value(
                    value
                )

                if value:

                    results.extend(
                        self.split_values(
                            value
                        )
                    )

                break

        return self.unique_items(
            results
        )

    # =====================================================
    # Job source
    # =====================================================

    def detect_job_source(
        self,
        page: Page,
        lines: list[str],
    ) -> str:

        url = self.normalize(
            page.url
        )

        known_sources = (
            "linkedin",
            "indeed",
            "gupy",
            "greenhouse",
            "lever",
            "workday",
            "smartrecruiters",
            "successfactors",
            "icims",
            "oracle",
            "ashby",
            "workable",
            "bamboohr",
            "jobvite",
            "taleo",
        )

        for source in known_sources:

            if source in url:

                return source

        text = self.normalize(
            " ".join(lines[:100])
        )

        for source in known_sources:

            if source in text:

                return source

        return ""

    # =====================================================
    # Application source
    # =====================================================

    def detect_application_source(
        self,
        application_url: str,
        page_url: str,
    ) -> str:

        if not application_url:

            return ""

        normalized = self.normalize(
            application_url
        )

        sources = (
            "linkedin",
            "indeed",
            "gupy",
            "greenhouse",
            "lever",
            "workday",
            "smartrecruiters",
            "successfactors",
            "icims",
            "oracle",
            "ashby",
            "workable",
            "bamboohr",
            "jobvite",
            "taleo",
        )

        for source in sources:

            if source in normalized:

                return source

        page_domain = self.get_domain(
            page_url
        )

        application_domain = self.get_domain(
            application_url
        )

        if (
            page_domain
            and application_domain
            and page_domain != application_domain
        ):

            return application_domain

        return ""

    # =====================================================
    # Section helpers
    # =====================================================

    def find_section_index(
        self,
        lines: list[str],
        section_names: tuple[str, ...],
    ) -> int:

        targets = {
            self.normalize(name)
            for name in section_names
        }

        for index, line in enumerate(
            lines
        ):

            normalized = self.normalize(
                line
            )

            normalized_without_colon = (
                normalized.rstrip(":")
            )

            if normalized in targets:

                return index

            if (
                normalized_without_colon
                in targets
            ):

                return index

        return -1

    def is_any_section_label(
        self,
        line: str,
    ) -> bool:

        normalized = (
            self.normalize(line)
            .rstrip(":")
        )

        targets = {
            self.normalize(item)
            .rstrip(":")
            for item in self.ALL_SECTION_LABELS
        }

        return normalized in targets

    def is_section_label(
        self,
        line: str,
        sections: tuple[str, ...],
    ) -> bool:

        normalized = (
            self.normalize(line)
            .rstrip(":")
        )

        targets = {
            self.normalize(item)
            .rstrip(":")
            for item in sections
        }

        return normalized in targets

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

        return any(
            marker in text
            for marker in self.PAGE_NOT_FOUND_MARKERS
        )

    def is_job_closed(
        self,
        lines: list[str],
    ) -> bool:

        text = self.normalize(
            " ".join(lines)
        )

        return any(
            marker in text
            for marker in self.CLOSED_MARKERS
        )

    # =====================================================
    # Text helpers
    # =====================================================

    @staticmethod
    def clean_line(
        line: str,
    ) -> str:

        value = re.sub(
            r"\s+",
            " ",
            line,
        ).strip()

        value = re.sub(
            r"^[•●▪◦‣\-–—]+\s*",
            "",
            value,
        ).strip()

        return value

    @staticmethod
    def clean_value(
        value: str,
    ) -> str:

        value = value.strip()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        value = value.rstrip(
            " ."
        )

        return value.strip()

    @staticmethod
    def normalize(
        value: str,
    ) -> str:

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip().casefold()

    def looks_like_label(
        self,
        line: str,
    ) -> bool:

        normalized = self.normalize(
            line
        )

        if normalized.endswith(":"):

            return True

        if self.is_any_section_label(
            line
        ):

            return True

        for labels in self.FIELD_LABELS.values():

            if normalized in {
                self.normalize(label)
                for label in labels
            }:

                return True

        return False

    def looks_like_footer(
        self,
        line: str,
    ) -> bool:

        normalized = self.normalize(
            line
        )

        footer_markers = (
            "get job alerts",
            "job alerts",
            "join our talent network",
            "join us",
            "search jobs",
            "register",
            "privacy policy",
            "terms of use",
            "cookie",
            "follow us",
        )

        return any(
            marker in normalized
            for marker in footer_markers
        )

    def clean_section_line(
        self,
        line: str,
    ) -> str:

        value = self.clean_line(
            line
        )

        if value in {
            ".",
            "|",
            "-",
            "–",
            "—",
        }:

            return ""

        return value

    def join_text(
        self,
        items: list[str],
    ) -> str:

        cleaned = []

        for item in items:

            item = self.clean_section_line(
                item
            )

            if item:

                cleaned.append(
                    item
                )

        return "\n".join(
            cleaned
        )

    def unique_items(
        self,
        items: list[str],
    ) -> list[str]:

        result = []

        seen = set()

        for item in items:

            cleaned = self.clean_section_line(
                item
            )

            if not cleaned:

                continue

            key = self.normalize(
                cleaned
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            result.append(
                cleaned
            )

        return result

    def append_unique(
        self,
        items: list[str],
        value: str,
    ) -> list[str]:

        result = list(items)

        normalized = self.normalize(
            value
        )

        if not any(
            self.normalize(item)
            == normalized
            for item in result
        ):

            result.append(
                value
            )

        return result

    def split_values(
        self,
        value: str,
    ) -> list[str]:

        parts = re.split(
            r"\s*[;,|]\s*",
            value,
        )

        return [
            self.clean_value(part)
            for part in parts
            if self.clean_value(part)
        ]

    def is_apply_text(
        self,
        text: str,
    ) -> bool:

        normalized = self.normalize(
            text
        )

        return any(
            re.search(
                pattern,
                normalized,
                flags=re.IGNORECASE,
            )
            for pattern in self.APPLY_TEXT_PATTERNS
        )

    def is_remote_value(
        self,
        value: str,
    ) -> bool:

        normalized = self.normalize(
            value
        )

        if normalized in {
            self.normalize(item)
            for item in self.REMOTE_TRUE
        }:

            return True

        return False

    # =====================================================
    # Company
    # =====================================================

    @staticmethod
    def clean_company(
        value: str,
    ) -> str:

        value = value.strip()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        value = re.sub(
            r"\s+(careers?|jobs?)$",
            "",
            value,
            flags=re.IGNORECASE,
        )

        return value.strip()

    # =====================================================
    # URL
    # =====================================================

    @staticmethod
    def get_domain(
        url: str,
    ) -> str:

        match = re.match(
            r"^(?:https?://)?([^/]+)",
            url,
            flags=re.IGNORECASE,
        )

        if not match:

            return ""

        return match.group(1).lower()
      # =====================================================
    # Gupy
    # =====================================================
    
    def is_gupy_url(
        self,
        url: str,
    ) -> bool:

        return "gupy" in self.normalize(url)