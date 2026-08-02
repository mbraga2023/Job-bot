from dataclasses import dataclass


@dataclass
class Job:

    id: int

    title: str

    company: str

    location: str

    level: str

    score: int

    link: str

    remote: bool