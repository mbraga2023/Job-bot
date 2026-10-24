"""Meu Padrinho page analyzer using Playwright."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class MeuPadrinhoAnalyzer:
    """Extrai informações de uma vaga do site Meu Padrinho usando Playwright."""

    STOP_SECTIONS = {
        "Tecnologias",
        "Requisitos",
        "Diferenciais",
        "Benefícios",
        "Outras Informações",
    }

    JOB_CONTENT_MARKERS = (
        "Sobre a vaga",
        "Tecnologias",
        "Requisitos",
        "Diferenciais",
        "Benefícios",
        "Candidatar-se agora",
    )

    CLOSED_MARKERS = (
        "vaga encerrada",
        "vaga fechada",
        "vaga não está mais disponível",
        "vaga nao esta mais disponivel",
        "não aceita mais candidaturas",
        "nao aceita mais candidaturas",
        "não está mais aceitando candidaturas",
        "nao esta mais aceitando candidaturas",
    )

    RATE_LIMIT_MARKERS = (
        "429 too many requests",
        "too many requests",
        "muitas requisições",
        "muitas requisicoes",
        "rate limit",
        "limite de requisições excedido",
        "limite de requisicoes excedido",
        "bloqueado temporariamente",
        "acesso bloqueado temporariamente",
        "bloqueio temporario",
        "bloqueio temporário",
        "temporarily blocked",
        "just a moment...",
    )

    LOGIN_URL_MARKERS = ("/login", "/log-in", "/signin", "/sign-in", "/entrar")

    LOGIN_REQUIRED_MARKERS = (
        "faça login para continuar",
        "faca login para continuar",
        "faça login para acessar",
        "faca login para acessar",
        "entre na sua conta para continuar",
        "acesse sua conta para continuar",
        "você precisa estar logado",
        "voce precisa estar logado",
        "you must be logged in",
        "log in to continue",
        "sign in to continue",
    )

    LEVELS = {
        "estágio",
        "estagio",
        "junior",
        "júnior",
        "pleno",
        "senior",
        "sênior",
        "especialista",
    }

    CONTRACTS = {
        "clt",
        "pj",
        "freelancer",
        "temporário",
        "temporario",
        "estágio",
        "estagio",
    }

    SOURCES = {
        "linkedin",
        "indeed",
        "gupy",
        "greenhouse",
        "catho",
    }

    async def analyze(self, page: Page) -> dict[str, Any]:
        response = getattr(page, "last_response", None)
        if response is not None and getattr(response, "status", None) == 429:
            return {
                "rate_limited": True,
                "status_code": 429,
                "page_not_found": False,
            }

        await self.wait_for_content(page)
        lines = await self.get_lines(page)

        if self.is_rate_limited(page, lines):
            return {
                "rate_limited": True,
                "status_code": getattr(response, "status", 429) if response else 429,
                "page_not_found": False,
            }

        if self.is_login_required(page, lines):
            return {
                "login_required": True,
                "page_not_found": False,
            }

        if self.is_page_not_found(lines):
            return {
                "page_not_found": True,
                "published_date": "",
                "title": "",
                "company": "",
                "location": "",
                "remote": False,
                "level": "",
                "contract": "",
                "job_source": "meupadrinho",
                "application_url": "",
                "application_source": "",
                "description": "",
                "technologies": [],
                "requirements": [],
                "differentials": [],
                "benefits": [],
                "job_status": "CLOSED",
            }

        closed = self.is_job_closed(lines)
        header_data = self.extract_header(lines)
        application_url = await self.get_apply_button(page)

        return {
            "page_not_found": False,
            **header_data,
            "job_source": header_data.get("job_source", "meupadrinho"),
            "application_url": application_url or page.url,
            "application_source": "meupadrinho",
            "description": self.extract_description(lines),
            "technologies": self.extract_section(lines, "Tecnologias"),
            "requirements": self.extract_section(lines, "Requisitos"),
            "differentials": self.extract_section(lines, "Diferenciais"),
            "benefits": self.extract_section(lines, "Benefícios"),
            "job_status": "CLOSED" if closed else "OPEN",
        }

    async def wait_for_content(self, page: Page) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except PlaywrightTimeoutError:
            pass

        for marker in self.JOB_CONTENT_MARKERS:
            try:
                locator = page.get_by_text(marker, exact=True).first
                await locator.wait_for(state="attached", timeout=2500)
                return
            except PlaywrightTimeoutError:
                continue

        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeoutError:
            pass

    async def get_lines(self, page: Page) -> list[str]:
        body = page.locator("body")
        await body.wait_for(state="attached")
        text = await body.inner_text()
        lines = []
        for raw_line in text.splitlines():
            line = self.clean_line(raw_line)
            if line:
                lines.append(line)
        return lines

    async def get_apply_button(self, page: Page) -> str:
        selectors = (
            page.get_by_role("button", name="Candidatar-se agora", exact=True),
            page.get_by_role("link", name="Candidatar-se agora", exact=True),
            page.get_by_text("Candidatar-se agora", exact=True),
        )

        for locator in selectors:
            count = await locator.count()
            if count == 0:
                continue
            for index in range(count):
                candidate = locator.nth(index)
                try:
                    if not await candidate.is_visible():
                        continue
                    href = await candidate.get_attribute("href")
                    if href:
                        return href
                except PlaywrightTimeoutError:
                    continue

        return ""

    def is_rate_limited(self, page: Page, lines: list[str]) -> bool:
        response = getattr(page, "last_response", None)
        if response is not None and getattr(response, "status", None) == 429:
            return True
        text = self.normalize(" ".join(lines))
        return any(marker in text for marker in self.RATE_LIMIT_MARKERS)

    def is_login_required(self, page: Page, lines: list[str]) -> bool:
        path = urlsplit(getattr(page, "url", "")).path.casefold().rstrip("/")
        if any(path.endswith(marker) for marker in self.LOGIN_URL_MARKERS):
            return True

        text = self.normalize(" ".join(lines))
        return any(marker in text for marker in self.LOGIN_REQUIRED_MARKERS)

    def is_page_not_found(self, lines: list[str]) -> bool:
        text = self.normalize(" ".join(lines))
        not_found_markers = (
            "page not found",
            "página não encontrada",
            "pagina nao encontrada",
            "vaga não encontrada",
            "vaga nao encontrada",
            "vaga não existe",
            "vaga nao existe",
            "404",
        )
        return any(marker in text for marker in not_found_markers)

    def is_job_closed(self, lines: list[str]) -> bool:
        text = self.normalize(" ".join(lines))
        return any(marker in text for marker in self.CLOSED_MARKERS)

    @staticmethod
    def clean_line(line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()

    @staticmethod
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    def find_index(self, lines: list[str], value: str) -> int:
        target = self.normalize(value)
        return next((index for index, line in enumerate(lines) if self.normalize(line) == target), -1)

    def extract_header(self, lines: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "published_date": "",
            "title": "",
            "company": "",
            "location": "",
            "remote": False,
            "level": "",
            "contract": "",
            "job_source": "meupadrinho",
        }

        published_index = next(
            (index for index, line in enumerate(lines) if self.normalize(line).startswith("publicado:")),
            -1,
        )
        if published_index == -1:
            return result

        published_line = lines[published_index]
        result["published_date"] = re.sub(r"^Publicado:\s*", "", published_line, flags=re.IGNORECASE).strip()

        data = []
        for line in lines[published_index + 1:]:
            if self.normalize(line) == self.normalize("Sobre a vaga"):
                break
            if line != "•":
                data.append(line)

        if not data:
            return result

        result["title"] = data[0]
        pointer = 1
        if pointer < len(data) and len(data[pointer]) == 1:
            pointer += 1
        if pointer < len(data):
            result["company"] = data[pointer]
            pointer += 1
        if pointer < len(data):
            result["location"] = data[pointer]
            pointer += 1

        remote_detected = False
        non_remote_detected = False
        for value in data[pointer:]:
            norm = self.normalize(value)
            if re.search(r"\b(?:presencial|hibrido|hybrid|onsite|on[- ]site)\b", norm):
                non_remote_detected = True
            elif re.search(r"\b(?:remoto|remote|home[- ]office|work from home)\b", norm):
                remote_detected = True
            elif norm in {self.normalize(item) for item in self.LEVELS}:
                result["level"] = value
            elif norm in {self.normalize(item) for item in self.CONTRACTS}:
                result["contract"] = value
            elif norm in {self.normalize(item) for item in self.SOURCES}:
                result["job_source"] = value

        result["remote"] = remote_detected and not non_remote_detected
        return result

    def extract_description(self, lines: list[str]) -> str:
        start = self.find_index(lines, "Sobre a vaga")
        if start == -1:
            return ""
        stop_sections = {self.normalize(section) for section in self.STOP_SECTIONS}
        items = []
        for line in lines[start + 1:]:
            if self.normalize(line) in stop_sections:
                break
            if line != "•":
                items.append(line)
        return "\n".join(items)

    def extract_section(self, lines: list[str], section: str) -> list[str]:
        start = self.find_index(lines, section)
        if start == -1:
            return []
        current = self.normalize(section)
        stop_sections = {self.normalize(item) for item in self.STOP_SECTIONS if self.normalize(item) != current}
        items = []
        for line in lines[start + 1:]:
            if self.normalize(line) in stop_sections:
                break
            if line != "•":
                items.append(line)
        return items
