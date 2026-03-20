"""Modelos de dados econômicos (saídas dos fetchers BCB, IBGE, etc.)."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class MacroIndicator(BaseModel):
    """Indicador macroeconômico pontual (Selic, IPCA, etc.)."""

    name: str
    value: float
    date: date
    source: str  # "bcb", "ibge"
    unit: Optional[str] = None  # "%", "R$", "índice"


class MacroSnapshot(BaseModel):
    """Conjunto de indicadores macro num momento."""

    indicators: list[MacroIndicator]
    timestamp: datetime


class MarketIndicator(BaseModel):
    """Indicador de mercado financeiro (IBOV, IFIX, etc.)."""

    name: str
    value: float
    date: date
    source: str  # "yahoo", "bcb"
    unit: Optional[str] = None


class MarketSnapshot(BaseModel):
    """Conjunto de indicadores de mercado num momento."""

    indicators: list[MarketIndicator]
    timestamp: datetime


class SectorIndicator(BaseModel):
    """Indicador de setor do mercado financeiro."""

    sector: str
    ticker: Optional[str] = None
    return_pct: Optional[float] = None
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    date: Optional[date] = None


class EconomicSectorIndicator(BaseModel):
    """Indicador de setor da economia real (PIB, emprego, etc.)."""

    sector: str
    gdp_share: Optional[float] = None
    employment: Optional[float] = None
    growth_rate: Optional[float] = None
    date: Optional[date] = None
    source: Optional[str] = None
