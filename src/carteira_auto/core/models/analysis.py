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


class CurrencyMetrics(BaseModel):
    """Métricas de câmbio e carry trade.

    Produzida por: CurrencyAnalyzer (analyze_currency)
    Fontes: BCBFetcher (PTAX, Selic), FREDFetcher (Fed Funds), YahooFinanceFetcher (DXY)
    """

    # ---- USD/BRL ----
    usd_brl: float | None = None
    """Dólar PTAX compra corrente — R$/USD | BCB SGS 10813."""

    usd_brl_ptax_venda: float | None = None
    """Dólar PTAX venda corrente — R$/USD | BCB SGS 1."""

    usd_brl_change_1m: float | None = None
    """Variação % do USD/BRL no último mês."""

    usd_brl_change_3m: float | None = None
    """Variação % do USD/BRL nos últimos 3 meses."""

    usd_brl_change_12m: float | None = None
    """Variação % do USD/BRL nos últimos 12 meses."""

    # ---- Dollar Index ----
    dxy: float | None = None
    """Dollar Index (DXY) corrente | Yahoo DX-Y.NYB."""

    dxy_change_1m: float | None = None
    """Variação % do DXY no último mês."""

    # ---- Carry trade ----
    selic_rate: float | None = None
    """Taxa Selic meta corrente — % a.a. | BCB SGS 432."""

    fed_funds_rate: float | None = None
    """Fed Funds Rate corrente — % a.a. | FRED DFF."""

    carry_spread: float | None = None
    """Spread Selic - Fed Funds em pp. Positivo = carry favorável ao BRL."""

    # ---- Câmbio real ----
    taxa_cambio_real_efetiva: float | None = None
    """Índice de taxa de câmbio real efetiva (IPCA) | BCB SGS 11752."""

    # ---- Sumário ----
    summary: str | None = None
    """Sumário textual do cenário cambial."""


class CommodityMetrics(BaseModel):
    """Métricas de commodities relevantes para carteira brasileira.

    Produzida por: CommodityAnalyzer (analyze_commodities)
    Fontes: YahooFinanceFetcher (futuros CL=F, BZ=F, GC=F, SI=F, ZS=F, ZC=F, ZW=F)
    """

    # ---- Petróleo ----
    oil_wti: float | None = None
    """Petróleo WTI corrente — USD/bbl | Yahoo CL=F."""

    oil_brent: float | None = None
    """Petróleo Brent corrente — USD/bbl | Yahoo BZ=F."""

    oil_change_1m: float | None = None
    """Variação % do Brent no último mês."""

    oil_change_3m: float | None = None
    """Variação % do Brent nos últimos 3 meses."""

    oil_change_12m: float | None = None
    """Variação % do Brent nos últimos 12 meses."""

    # ---- Metais ----
    gold: float | None = None
    """Ouro corrente — USD/oz | Yahoo GC=F."""

    gold_change_1m: float | None = None
    """Variação % do ouro no último mês."""

    gold_change_3m: float | None = None
    """Variação % do ouro nos últimos 3 meses."""

    gold_change_12m: float | None = None
    """Variação % do ouro nos últimos 12 meses."""

    silver: float | None = None
    """Prata corrente — USD/oz | Yahoo SI=F."""

    silver_change_1m: float | None = None
    """Variação % da prata no último mês."""

    # ---- Agrícolas ----
    soybean: float | None = None
    """Soja corrente — USD/bushel | Yahoo ZS=F."""

    soybean_change_1m: float | None = None
    """Variação % da soja no último mês."""

    soybean_change_3m: float | None = None
    """Variação % da soja nos últimos 3 meses."""

    corn: float | None = None
    """Milho corrente — USD/bushel | Yahoo ZC=F."""

    wheat: float | None = None
    """Trigo corrente — USD/bushel | Yahoo ZW=F."""

    # ---- Indicadores compostos ----
    commodity_index_change_3m: float | None = None
    """Variação média ponderada das commodities em 3m (proxy para ciclo)."""

    cycle_signal: str | None = None
    """Sinal do ciclo de commodities: 'expansion', 'peak', 'contraction', 'trough'."""

    # ---- Sumário ----
    summary: str | None = None
    """Sumário textual do cenário de commodities."""


class FiscalMetrics(BaseModel):
    """Métricas fiscais do governo brasileiro.

    Produzida por: FiscalAnalyzer (analyze_fiscal)
    Fontes: BCBFetcher (séries SGS 13762, 4503, 5793, 4649, 5727)
    """

    # ---- Dívida ----
    divida_bruta_pib: float | None = None
    """Dívida Bruta do Governo Geral / PIB — % | BCB SGS 13762."""

    divida_liquida_pib: float | None = None
    """Dívida Líquida do Setor Público / PIB — % | BCB SGS 4503."""

    # ---- Resultado fiscal ----
    resultado_primario_pib: float | None = None
    """Resultado Primário acumulado 12m / PIB — % | BCB SGS 5793."""

    resultado_nominal: float | None = None
    """Resultado Nominal acumulado 12m — R$ milhões | BCB SGS 4649."""

    juros_nominais_pib: float | None = None
    """Juros Nominais acumulados 12m / PIB — % | BCB SGS 5727."""

    # ---- Variação temporal ----
    divida_bruta_pib_change_12m: float | None = None
    """Variação da dívida bruta/PIB em 12 meses — pp."""

    resultado_primario_pib_change_12m: float | None = None
    """Variação do resultado primário/PIB em 12 meses — pp."""

    # ---- Avaliação ----
    fiscal_trajectory: str | None = None
    """Avaliação da trajetória fiscal: 'improving', 'stable', 'warning', 'deteriorating', 'critical', 'severe'."""

    # ---- Sumário ----
    summary: str | None = None
    """Sumário textual da situação fiscal."""


class RebalanceRecommendation(BaseModel):
    """Recomendação de rebalanceamento para um ativo."""

    ticker: str
    action: Literal["comprar", "vender"]
    quantity: float | None = None
    value: float | None = None
    reason: str | None = None
