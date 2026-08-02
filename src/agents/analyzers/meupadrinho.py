from __future__ import annotations

import re
from typing import Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class MeuPadrinhoAnalyzer:
    """Extrai informações de uma vaga do site Meu Padrinho usando Playwright."""

    STOP_SECTIONS = {
        "Tecnologias",
        "Requisitos",
        "Diferenciais",
        "Outras Informações",
    }

    JOB_CONTENT_MARKERS = (
        "Sobre a vaga",
        "Tecnologias",
        "Requisitos",
        "Diferenciais",
        "Candidatar-se agora",
    )

    async def analyze(self, page: Page) -> dict[str, Any]:
        """Analisa a página e retorna somente valores serializáveis."""
        await self.wait_for_content(page)
        lines = await self.get_lines(page)

        return {
            "title": self.extract_title(lines),
            "company": self.extract_company(lines),
            "location": self.extract_location(lines),
            "remote": self.extract_remote(lines),
            "level": self.extract_level(lines),
            "contract": self.extract_contract(lines),
            "source": self.extract_source(lines),
            "description": self.extract_description(lines),
            "technologies": self.extract_section(lines, "Tecnologias"),
            "requirements": self.extract_section(lines, "Requisitos"),
            "differentials": self.extract_section(lines, "Diferenciais"),
            "apply_button": await self.get_apply_button(page),
        }

    # ---------------------------------------------------
    # Playwright / coleta
    # ---------------------------------------------------

    async def wait_for_content(self, page: Page) -> None:
        """Aguarda a renderização do conteúdo sem falhar em páginas variantes."""
        try:
            await page.wait_for_load_state("domcontentloaded")
        except PlaywrightTimeoutError:
            pass

        # Aguarda algum marcador conhecido da página.
        for marker in self.JOB_CONTENT_MARKERS:
            try:
                await page.get_by_text(marker, exact=True).first.wait_for(
                    state="attached",
                    timeout=2500,
                )
                return
            except PlaywrightTimeoutError:
                continue

        # Fallback para aplicações que alteram o texto depois do carregamento.
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeoutError:
            pass

    async def get_lines(self, page: Page) -> list[str]:
        text = await page.locator("body").inner_text()

        lines = [
            self.clean_line(line)
            for line in text.splitlines()
            if self.clean_line(line)
        ]

        # Diagnóstico opcional. Ative com ANALYZER_DEBUG=1.
        # Não imprime dados por padrão para evitar poluir o output da automação.
        import os

        if os.getenv("ANALYZER_DEBUG") == "1":
            print(f"URL: {page.url}")
            print(f"Tamanho do texto: {len(text)}")
            print("Linhas extraídas:")
            for index, line in enumerate(lines):
                print(f"{index}: {line!r}")

        return lines

    async def get_apply_button(self, page: Page) -> bool:
        """Retorna bool, nunca um Locator, para permitir serialização em JSON."""
        button = page.get_by_role(
            "button",
            name="Candidatar-se agora",
            exact=True,
        )

        if await button.count() > 0:
            return await button.first.is_visible()

        # Em algumas páginas a ação pode ser renderizada como link.
        link = page.get_by_role(
            "link",
            name="Candidatar-se agora",
            exact=True,
        )

        if await link.count() > 0:
            return await link.first.is_visible()

        # Último fallback para diferenças pequenas no HTML/role.
        text_locator = page.get_by_text(
            "Candidatar-se agora",
            exact=True,
        )

        return await text_locator.count() > 0

    # ---------------------------------------------------
    # Helpers
    # ---------------------------------------------------

    @staticmethod
    def clean_line(line: str) -> str:
        line = re.sub(r"\s+", " ", line)
        return line.strip()

    @staticmethod
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    def find_index(self, lines: list[str], value: str) -> int:
        target = self.normalize(value)

        for index, line in enumerate(lines):
            if self.normalize(line) == target:
                return index

        return -1

    def find_after(
        self,
        lines: list[str],
        value: str,
        offset: int = 1,
    ) -> str:
        index = self.find_index(lines, value)
        target_index = index + offset

        if index == -1 or target_index >= len(lines):
            return ""

        return lines[target_index]

    # ---------------------------------------------------
    # Main fields
    # ---------------------------------------------------

    def extract_title(self, lines: list[str]) -> str:
        keywords = (
            "quality assurance",
            "test analyst",
            "tester",
        )

        for line in lines:
            normalized = self.normalize(line)

            # Evita considerar uma frase qualquer apenas porque contém "qa".
            if any(keyword in normalized for keyword in keywords):
                return line

            if re.search(r"\bqa\b", normalized):
                return line

        return ""

    def extract_company(self, lines: list[str]) -> str:
        title = self.extract_title(lines)
        return self.find_after(lines, title) if title else ""

    def extract_location(self, lines: list[str]) -> str:
        title = self.extract_title(lines)
        if not title:
            return ""

        title_index = self.find_index(lines, title)
        company = self.extract_company(lines)

        if not company:
            return ""

        company_index = self.find_index(lines[title_index + 1 :], company)
        if company_index == -1:
            return ""

        location_index = title_index + 1 + company_index + 1
        return lines[location_index] if location_index < len(lines) else ""

    def extract_remote(self, lines: list[str]) -> bool:
        return any(
            "remoto" in self.normalize(line)
            or "remote" in self.normalize(line)
            for line in lines
        )

    def extract_level(self, lines: list[str]) -> str:
        levels = {
            "estágio",
            "estagio",
            "junior",
            "júnior",
            "pleno",
            "senior",
            "sênior",
            "especialista",
        }

        for line in lines:
            if self.normalize(line) in levels:
                return line

        return ""

    def extract_contract(self, lines: list[str]) -> str:
        contracts = {
            "pj",
            "clt",
            "freelancer",
            "temporário",
            "temporario",
            "estágio",
            "estagio",
        }

        for line in lines:
            if self.normalize(line) in contracts:
                return line

        return ""

    def extract_source(self, lines: list[str]) -> str:
        sources = {
            "linkedin",
            "gupy",
            "greenhouse",
            "indeed",
            "catho",
        }

        for line in lines:
            if self.normalize(line) in sources:
                return line

        return ""

    # ---------------------------------------------------
    # Sections
    # ---------------------------------------------------

    def extract_description(self, lines: list[str]) -> str:
        start = self.find_index(lines, "Sobre a vaga")

        if start == -1:
            return ""

        items: list[str] = []
        stop_sections = {
            self.normalize(section)
            for section in self.STOP_SECTIONS
        }

        for line in lines[start + 1 :]:
            if self.normalize(line) in stop_sections:
                break

            if line != "•":
                items.append(line)

        return "\n".join(items)

    def extract_section(
        self,
        lines: list[str],
        section: str,
    ) -> list[str]:
        start = self.find_index(lines, section)

        if start == -1:
            return []

        stop_sections = {
            self.normalize(item)
            for item in self.STOP_SECTIONS
            if self.normalize(item) != self.normalize(section)
        }

        items: list[str] = []

        for line in lines[start + 1 :]:
            if self.normalize(line) in stop_sections:
                break

            if line != "•":
                items.append(line)

        return items
