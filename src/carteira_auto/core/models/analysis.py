"""Modelos de saída dos analyzers."""

from typing import Literal

from pydantic import BaseModel


class AllocationResult(BaseModel):
    """Resultado de alocação por classe de ativo."""

    asset_class: str
    current_pct: float
    target_pct: float
    deviation: float
    action: Literal["comprar", "vender", "manter"] | None = None


class PortfolioMetrics(BaseModel):
    """Métricas consolidadas da carteira."""

    total_value: float
    total_cost: float
    total_return: float
    total_return_pct: float
    dividend_yield: float | None = None
    allocations: list[AllocationResult] = []


class RiskMetrics(BaseModel):
    """Métricas de risco da carteira."""

    volatility: float | None = None
    var_95: float | None = None
    var_99: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    beta: float | None = None

    def is_complete(self) -> bool:
        """Verifica se todas as métricas de risco foram calculadas."""
        return all(
            v is not None
            for v in [
                self.volatility,
                self.var_95,
                self.var_99,
                self.sharpe_ratio,
                self.max_drawdown,
                self.beta,
            ]
        )


class MarketMetrics(BaseModel):
    """Métricas de benchmarks de mercado."""

    ibov_return: float | None = None
    ifix_return: float | None = None
    cdi_return: float | None = None


class MacroContext(BaseModel):
    """Contexto macroeconômico consolidado."""

    selic: float | None = None
    ipca: float | None = None
    cambio: float | None = None
    pib_growth: float | None = None
    summary: str | None = None


class RebalanceRecommendation(BaseModel):
    """Recomendação de rebalanceamento para um ativo."""

    ticker: str
    action: Literal["comprar", "vender"]
    quantity: float | None = None
    value: float | None = None
    reason: str | None = None
