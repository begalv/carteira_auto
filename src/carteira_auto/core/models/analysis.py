"""Modelos de saída dos analyzers."""

from typing import Optional

from pydantic import BaseModel


class AllocationResult(BaseModel):
    """Resultado de alocação por classe de ativo."""

    asset_class: str
    current_pct: float
    target_pct: float
    deviation: float
    action: Optional[str] = None  # "comprar", "vender", "manter"


class PortfolioMetrics(BaseModel):
    """Métricas consolidadas da carteira."""

    total_value: float
    total_cost: float
    total_return: float
    total_return_pct: float
    dividend_yield: Optional[float] = None
    allocations: list[AllocationResult] = []


class RiskMetrics(BaseModel):
    """Métricas de risco da carteira."""

    volatility: Optional[float] = None
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    beta: Optional[float] = None


class MarketMetrics(BaseModel):
    """Métricas de benchmarks de mercado."""

    ibov_return: Optional[float] = None
    ifix_return: Optional[float] = None
    cdi_return: Optional[float] = None


class MacroContext(BaseModel):
    """Contexto macroeconômico consolidado."""

    selic: Optional[float] = None
    ipca: Optional[float] = None
    cambio: Optional[float] = None
    pib_growth: Optional[float] = None
    summary: Optional[str] = None


class RebalanceRecommendation(BaseModel):
    """Recomendação de rebalanceamento para um ativo."""

    ticker: str
    action: str  # "comprar", "vender"
    quantity: Optional[float] = None
    value: Optional[float] = None
    reason: Optional[str] = None
