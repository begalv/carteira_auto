"""Módulo de fetchers para coleta de dados."""

from .bcb_fetcher import BCBFetcher
from .ddm_fetcher import DDMFetcher
from .ibge_fetcher import IBGEFetcher
from .yahoo_fetcher import YahooFinanceFetcher

__all__ = [
    "YahooFinanceFetcher",
    "BCBFetcher",
    "IBGEFetcher",
    "DDMFetcher",
]
