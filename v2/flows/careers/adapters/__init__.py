"""Career Portal Crawling Adapters."""

from v2.flows.careers.adapters.base import BaseCareerAdapter, CareerJobItem, CareerPageModel
from v2.flows.careers.adapters.generic import GenericAdapter
from v2.flows.careers.adapters.gupy import GupyAdapter
from v2.flows.careers.adapters.inhire import InHireAdapter

__all__ = [
    "BaseCareerAdapter",
    "CareerJobItem",
    "CareerPageModel",
    "GenericAdapter",
    "GupyAdapter",
    "InHireAdapter",
]
