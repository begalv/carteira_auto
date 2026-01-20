"""
carteira_auto - Sistema de automação e análise de carteiras de investimentos
"""

__version__ = "0.1.0"
__author__ = "Bernardo Galvão"
__email__ = "bgalvaods@gmail.com"

from carteira_auto.config import settings
from carteira_auto.core.portfolio import Portfolio
from carteira_auto.data.fetchers import YahooFinanceFetcher
from carteira_auto.analyzers import PortfolioMetrics

__all__ = [
    "Portfolio",
    "YahooFinanceFetcher",
    "PortfolioMetrics",
    "settings",
]