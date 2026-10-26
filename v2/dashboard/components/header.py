"""Shared dashboard page header."""

from typing import Literal


def render_header(
    active_page: Literal["dashboard", "companies"],
    actions_html: str = "",
) -> str:
    """Render the shared site title and page navigation."""
    dashboard_link = (
        '<a href="/" class="active" aria-current="page">Dashboard</a>'
        if active_page == "dashboard"
        else '<a href="/">Dashboard</a>'
    )
    companies_link = (
        '<a href="/companies" class="active" aria-current="page">Companies</a>'
        if active_page == "companies"
        else '<a href="/companies">Companies</a>'
    )
    actions = f'<div class="header-actions">{actions_html}</div>' if actions_html else ""
    return f"""<header class="site-header">
    <h1>Job-bot <span>Version 2.0</span></h1>
    <nav class="tabs" aria-label="Main navigation">
      {dashboard_link}
      {companies_link}
    </nav>
    {actions}
  </header>"""
