"""Analyzer de commodities relevantes para carteira brasileira.

Node DAG: name="analyze_commodities", deps=[]
Produz: ctx["commodity_metrics"] -> CommodityMetrics
"""

import traceback

import pandas as pd

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import CommodityMetrics
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)

# Tickers Yahoo Finance para commodities
COMMODITY_TICKERS: dict[str, str] = {
    "CL=F": "oil_wti",
    "BZ=F": "oil_brent",
    "GC=F": "gold",
    "SI=F": "silver",
    "ZS=F": "soybean",
    "ZC=F": "corn",
    "ZW=F": "wheat",
}

# Pesos para o índice composto de commodities (variação 3m).
# Brent é o benchmark global de referência para petróleo (WTI é US-cêntrico);
# peso de óleo concentrado no Brent para evitar dupla contagem.
COMMODITY_WEIGHTS: dict[str, float] = {
    "oil_brent": 0.50,
    "gold": 0.20,
    "soybean": 0.20,
    "silver": 0.10,
}

# Tickers principais para cálculo do ciclo (comparação com média 5y)
CYCLE_TICKERS: list[str] = ["BZ=F", "GC=F", "ZS=F"]


class CommodityAnalyzer(Node):
    """Analisa preços de commodities, variações e ciclo.

    Não depende de outros nodes — busca dados diretamente do Yahoo Finance.
    Falhas parciais são registradas em ctx["_errors"] mas não impedem
    o retorno dos indicadores obtidos com sucesso.

    Produz no contexto:
        - "commodity_metrics": CommodityMetrics
    """

    name = "analyze_commodities"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        metrics = self._build_commodity_metrics(ctx)
        ctx["commodity_metrics"] = metrics
        logger.info(
            f"Commodities: Brent={metrics.oil_brent}, Ouro={metrics.gold}, "
            f"Soja={metrics.soybean}, ciclo={metrics.cycle_signal}"
            if metrics.oil_brent is not None
            else f"Commodities: {metrics.summary}"
        )
        return ctx

    def _build_commodity_metrics(self, ctx: PipelineContext) -> CommodityMetrics:
        """Busca preços de commodities e calcula métricas."""
        from carteira_auto.data.fetchers.yahoo_fetcher import YahooFinanceFetcher

        ctx.setdefault("_errors", {})
        errors: list[str] = []

        prices: dict[str, float | None] = {}
        changes_1m: dict[str, float | None] = {}
        changes_3m: dict[str, float | None] = {}
        changes_12m: dict[str, float | None] = {}

        yahoo = YahooFinanceFetcher()

        # ---- Buscar dados históricos 5y para preços + ciclo ----
        try:
            tickers = list(COMMODITY_TICKERS.keys())
            data = yahoo.get_historical_price_data(tickers, period="5y")

            if not data.empty:
                for ticker, field_name in COMMODITY_TICKERS.items():
                    try:
                        close = self._extract_close(data, ticker)
                        if close is not None and not close.empty:
                            prices[field_name] = float(close.iloc[-1])
                            changes_1m[field_name] = self._pct_change(close, 21)
                            changes_3m[field_name] = self._pct_change(close, 63)
                            changes_12m[field_name] = self._pct_change(close, 252)
                    except Exception as e:
                        logger.warning(f"Falha ao processar {ticker}: {e}")
                        errors.append(f"{ticker}: {e}")
            else:
                errors.append("Yahoo retornou DataFrame vazio para commodities")

        except Exception as e:
            logger.error(f"Falha ao buscar commodities: {e}\n{traceback.format_exc()}")
            errors.append(f"Yahoo commodities: {e}")

        # ---- Calcular índice composto 3m ----
        commodity_index_change_3m = self._calc_weighted_index(changes_3m)

        # ---- Calcular cycle signal (comparação com média 5y) ----
        cycle_signal = None
        try:
            if not data.empty:
                cycle_signal = self._calc_cycle_signal(data)
        except Exception:
            pass  # Ciclo é informativo, não crítico

        if errors:
            ctx["_errors"]["analyze_commodities.partial"] = "; ".join(errors)

        summary = self._generate_summary(prices, cycle_signal)

        return CommodityMetrics(
            oil_wti=prices.get("oil_wti"),
            oil_brent=prices.get("oil_brent"),
            oil_change_1m=changes_1m.get("oil_brent"),
            oil_change_3m=changes_3m.get("oil_brent"),
            oil_change_12m=changes_12m.get("oil_brent"),
            gold=prices.get("gold"),
            gold_change_1m=changes_1m.get("gold"),
            gold_change_3m=changes_3m.get("gold"),
            gold_change_12m=changes_12m.get("gold"),
            silver=prices.get("silver"),
            silver_change_1m=changes_1m.get("silver"),
            soybean=prices.get("soybean"),
            soybean_change_1m=changes_1m.get("soybean"),
            soybean_change_3m=changes_3m.get("soybean"),
            corn=prices.get("corn"),
            wheat=prices.get("wheat"),
            commodity_index_change_3m=commodity_index_change_3m,
            cycle_signal=cycle_signal,
            summary=summary,
        )

    @staticmethod
    def _extract_close(data: pd.DataFrame, ticker: str) -> pd.Series | None:
        """Extrai série Close de um ticker do DataFrame multi-ticker."""
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker in data.columns.get_level_values(0):
                    close = data[(ticker, "Close")].dropna()
                    return close
                elif ticker in data.columns.get_level_values(1):
                    close = data[("Close", ticker)].dropna()
                    return close
            elif "Close" in data.columns:
                return data["Close"].dropna()
        except (KeyError, TypeError):
            pass
        return None

    @staticmethod
    def _pct_change(series: pd.Series, lookback: int) -> float | None:
        """Calcula variação percentual vs N períodos atrás."""
        if len(series) <= lookback:
            return None
        current = float(series.iloc[-1])
        past = float(series.iloc[-lookback - 1])
        if past == 0:
            return None
        return round((current - past) / past * 100, 2)

    @staticmethod
    def _calc_weighted_index(changes_3m: dict[str, float | None]) -> float | None:
        """Calcula índice composto ponderado de variação 3m."""
        total_weight = 0.0
        weighted_sum = 0.0

        for field, weight in COMMODITY_WEIGHTS.items():
            change = changes_3m.get(field)
            if change is not None:
                weighted_sum += change * weight
                total_weight += weight

        if total_weight == 0:
            return None
        return round(weighted_sum / total_weight, 2)

    @staticmethod
    def _calc_cycle_signal(data: pd.DataFrame) -> str | None:
        """Determina sinal do ciclo comparando preço atual vs média 5y."""
        ratios = []

        for ticker in CYCLE_TICKERS:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if ticker in data.columns.get_level_values(0):
                        close = data[(ticker, "Close")].dropna()
                    elif ticker in data.columns.get_level_values(1):
                        close = data[("Close", ticker)].dropna()
                    else:
                        continue
                elif "Close" in data.columns:
                    close = data["Close"].dropna()
                else:
                    continue

                if len(close) < 252:  # Mínimo 1 ano de dados
                    continue

                current = float(close.iloc[-1])
                mean_5y = float(close.mean())
                if mean_5y > 0:
                    ratios.append(current / mean_5y)
            except (KeyError, TypeError):
                continue

        if not ratios:
            return None

        avg_ratio = sum(ratios) / len(ratios)

        if avg_ratio > 1.20:
            return "expansion"
        elif avg_ratio > 1.00:
            return "peak"
        elif avg_ratio > 0.80:
            return "contraction"
        else:
            return "trough"

    @staticmethod
    def _generate_summary(prices: dict[str, float | None], cycle: str | None) -> str:
        """Gera sumário textual do cenário de commodities."""
        parts = []
        if prices.get("oil_brent") is not None:
            parts.append(f"Brent US${prices['oil_brent']:.1f}")
        if prices.get("gold") is not None:
            parts.append(f"Ouro US${prices['gold']:.0f}")
        if prices.get("soybean") is not None:
            parts.append(f"Soja US${prices['soybean']:.0f}")
        if cycle is not None:
            parts.append(f"ciclo={cycle}")
        return "; ".join(parts) if parts else "Dados de commodities indisponíveis"
