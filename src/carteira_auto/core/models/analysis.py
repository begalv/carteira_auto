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
    """Volatilidade anualizada da carteira (desvio padrão — % a.a.)."""

    var_95: float | None = None
    """Value at Risk com 95% de confiança (perda diária máxima esperada — %)."""

    var_99: float | None = None
    """Value at Risk com 99% de confiança (perda diária máxima esperada — %)."""

    sharpe_ratio: float | None = None
    """Índice de Sharpe anualizado (retorno excedente / volatilidade — adimensional)."""

    max_drawdown: float | None = None
    """Máximo drawdown da carteira no período (queda de pico a vale — %)."""

    beta: float | None = None
    """Beta da carteira em relação ao IBOV (sensibilidade ao mercado — adimensional)."""

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
    """Métricas de benchmarks de mercado no período de análise."""

    ibov_return: float | None = None
    """Retorno total do IBOV no período (% acumulado)."""

    ifix_return: float | None = None
    """Retorno total do IFIX (índice de FIIs) no período (% acumulado)."""

    cdi_return: float | None = None
    """Retorno acumulado do CDI no período (% acumulado — composição diária)."""

    sp500_return: float | None = None
    """Retorno total do S&P 500 no período em USD (% acumulado)."""

    dolar_retorno: float | None = None
    """Variação do dólar (BRL/USD) no período (% acumulado)."""

    ouro_retorno: float | None = None
    """Variação do ouro (GC=F) no período em USD (% acumulado)."""

    selic_retorno: float | None = None
    """Retorno estimado da Selic no período (% acumulado — composição diária da meta)."""

    brl_usd: float | None = None
    """Taxa de câmbio BRL/USD corrente (PTAX venda — R$ por USD)."""


class MacroContext(BaseModel):
    """Contexto macroeconômico consolidado — indicadores BCB e IBGE."""

    # ---- Taxas de juros ----
    selic: float | None = None
    """Taxa Selic meta — % a.a. | Divulgação: reuniões COPOM (~8×/ano) | Fonte: BCB SGS 432."""

    cdi: float | None = None
    """CDI acumulado 12 meses — % a.a. (composição de taxas % a.d.) | Diário | Fonte: BCB SGS 12."""

    poupanca: float | None = None
    """Rendimento da poupança acumulado 12 meses — % a.a. (composição de taxas % a.m.) | Mensal | Fonte: BCB SGS 25."""

    tr: float | None = None
    """Taxa Referencial (TR) acumulada 12 meses — % a.a. (composição de taxas % a.m.) | Mensal | Fonte: BCB SGS 226."""

    # ---- Inflação ----
    ipca: float | None = None
    """IPCA acumulado 12 meses — % (composição de variações mensais) | Mensal | Fonte: BCB SGS 433."""

    igpm: float | None = None
    """IGP-M acumulado 12 meses — % (composição de variações mensais) | Mensal | Fonte: BCB SGS 189."""

    inpc: float | None = None
    """INPC acumulado 12 meses — % (composição de variações mensais) | Mensal | Fonte: BCB SGS 188."""

    # ---- Câmbio ----
    cambio: float | None = None
    """Dólar PTAX compra — R$ por USD | Dias úteis | Fonte: BCB SGS 10813."""

    dolar_ptax_venda: float | None = None
    """Dólar PTAX venda — R$ por USD | Dias úteis | Fonte: BCB SGS 1."""

    # ---- Atividade econômica ----
    pib_growth: float | None = None
    """PIB — variação % vs mesmo trimestre do ano anterior | Trimestral | Fonte: IBGE SIDRA 5932."""

    desocupacao: float | None = None
    """Taxa de desocupação PNAD Contínua — % | Trimestral móvel | Fonte: IBGE SIDRA 6381."""

    # ---- Sumário ----
    summary: str | None = None
    """Sumário textual do cenário macro gerado automaticamente."""


class RebalanceRecommendation(BaseModel):
    """Recomendação de rebalanceamento para um ativo."""

    ticker: str
    action: Literal["comprar", "vender"]
    quantity: float | None = None
    value: float | None = None
    reason: str | None = None
