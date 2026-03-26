"""Analyzer de mercado — benchmarks (IBOV, IFIX, CDI).

Node DAG: name="analyze_market", deps=[]
Produz: ctx["market_metrics"] -> MarketMetrics
"""

import traceback

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import MarketMetrics
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class MarketAnalyzer(Node):
    """Calcula retornos dos benchmarks de mercado.

    Não depende de outros nodes — busca dados diretamente.
    Falhas parciais são registradas em ctx["_errors"].

    Produz no contexto:
        - "market_metrics": MarketMetrics
    """

    name = "analyze_market"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        metrics = self._fetch_benchmarks(ctx)
        ctx["market_metrics"] = metrics
        logger.info(
            f"Mercado: IBOV={metrics.ibov_return}, "
            f"IFIX={metrics.ifix_return}, "
            f"CDI={metrics.cdi_return}"
        )
        return ctx

    def _fetch_benchmarks(self, ctx: PipelineContext) -> MarketMetrics:
        """Busca retornos dos principais benchmarks."""
        from carteira_auto.data.fetchers import BCBFetcher, YahooFinanceFetcher

        ctx.setdefault("_errors", {})
        errors: list[str] = []

        ibov_return = None
        ifix_return = None
        cdi_return = None

        yahoo = YahooFinanceFetcher()

        # IBOV via Yahoo
        try:
            ibov_data = yahoo.get_historical_price_data(
                ["^BVSP"], period="1y", interval="1d"
            )
            if not ibov_data.empty and "Close" in ibov_data.columns:
                closes = ibov_data["Close"].dropna()
                if len(closes) >= 2:
                    ibov_return = (closes.iloc[-1] / closes.iloc[0]) - 1
        except Exception as e:
            logger.error(f"Falha ao buscar IBOV: {e}\n{traceback.format_exc()}")
            errors.append(f"IBOV: {e}")

        # IFIX via Yahoo
        try:
            ifix_data = yahoo.get_historical_price_data(
                ["IFIX.SA"], period="1y", interval="1d"
            )
            if not ifix_data.empty and "Close" in ifix_data.columns:
                closes = ifix_data["Close"].dropna()
                if len(closes) >= 2:
                    ifix_return = (closes.iloc[-1] / closes.iloc[0]) - 1
        except Exception as e:
            logger.error(f"Falha ao buscar IFIX: {e}\n{traceback.format_exc()}")
            errors.append(f"IFIX: {e}")

        # CDI acumulado via BCB
        try:
            bcb = BCBFetcher()
            cdi_df = bcb.get_cdi(period_days=365)
            if not cdi_df.empty:
                daily_rates = cdi_df["valor"] / 100
                cdi_return = ((1 + daily_rates).prod()) - 1
        except Exception as e:
            logger.error(f"Falha ao buscar CDI: {e}\n{traceback.format_exc()}")
            errors.append(f"CDI: {e}")

        if errors:
            ctx["_errors"]["analyze_market.partial"] = "; ".join(errors)

        return MarketMetrics(
            ibov_return=ibov_return,
            ifix_return=ifix_return,
            cdi_return=cdi_return,
        )
