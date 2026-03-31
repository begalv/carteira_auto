"""Módulo de fetchers para coleta de dados."""

from .bcb import BCBFetcher
from .cvm_fetcher import CVMFetcher
from .ddm_fetcher import DDMFetcher
from .fred_fetcher import FREDFetcher
from .ibge_fetcher import IBGEFetcher
from .tesouro_fetcher import TesouroDiretoFetcher
from .yahoo_fetcher import YahooFinanceFetcher

__all__ = [
    "YahooFinanceFetcher",
    "BCBFetcher",
    "IBGEFetcher",
    "DDMFetcher",
    "CVMFetcher",
    "FREDFetcher",
    "TesouroDiretoFetcher",
]
