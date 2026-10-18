from agents.platforms.base import (
    BaseCareerAdapter,
    CareerPageModel,
)

INHIRE_MODEL = CareerPageModel(
    platform="inhire",
    search_input=[
        "input#name",
        'input[name="name"]',
        'input[placeholder="Search by job name"]',
    ],
    search_button=[],
    job_links=['a[href^="/vagas/"]'],
    job_cards=['li:has(a[href^="/vagas/"])'],
    next_page=[],
)


class InHireAdapter(BaseCareerAdapter):
    def __init__(self, page):
        super().__init__(page, INHIRE_MODEL)
