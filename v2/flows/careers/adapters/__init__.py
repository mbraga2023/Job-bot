"""Career Portal Crawling Adapters."""

from v2.flows.careers.adapters.base import BaseCareerAdapter, CareerJobItem, CareerPageModel
from v2.flows.careers.adapters.conquestone import ConquestOneAdapter
from v2.flows.careers.adapters.generic import GenericAdapter
from v2.flows.careers.adapters.gupy import GupyAdapter
from v2.flows.careers.adapters.inhire import InHireAdapter
from v2.flows.careers.adapters.mindsight import MindsightAdapter

__all__ = [
    "BaseCareerAdapter",
    "CareerJobItem",
    "CareerPageModel",
    "ConquestOneAdapter",
    "GenericAdapter",
    "GupyAdapter",
    "InHireAdapter",
    "MindsightAdapter",
]
