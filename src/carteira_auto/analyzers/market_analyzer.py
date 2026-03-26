"""Analyzer de mercado — benchmarks (IBOV, IFIX, CDI, S&P 500, dólar, ouro, Selic).

Node DAG: name="analyze_market", deps=[]
Produz: ctx["market_metrics"] -> MarketMetrics

Benchmarks coletados:
    Renda variável BR:   IBOV (^BVSP), IFIX (IFIX.SA)
    Renda fixa BR:       CDI acumulado (BCB SGS 12), Selic acumulada (BCB SGS 432)
    Internacional:       S&P 500 (^GSPC), Ouro (GC=F)
    Câmbio:              Dólar/BRL variação (BRL=X), PTAX compra atual (BCB SGS 10813)
"""

import traceback

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import MarketMetrics
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class MarketAnalyzer(Node):
    """Calcula retornos de todos os benchmarks de mercado relevantes.

    Não depende de outros nodes — busca dados diretamente.
    Falhas parciais são registradas em ctx["_errors"] mas não impedem
    o retorno dos benchmarks obtidos com sucesso.

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
            f"Mercado: IBOV={metrics.ibov_return:.1%}, "
            f"CDI={metrics.cdi_return:.1%}, "
            f"S&P500={metrics.sp500_return}, "
            f"USD={metrics.brl_usd}"
            if metrics.ibov_return is not None and metrics.cdi_return is not None
            else "Mercado: dados parcialmente indisponíveis"
        )
        return ctx

    def _fetch_benchmarks(self, ctx: PipelineContext) -> MarketMetrics:
        """Busca retornos acumulados dos principais benchmarks no período de 5 anos."""
        from carteira_auto.data.fetchers import BCBFetcher, YahooFinanceFetcher

        ctx.setdefault("_errors", {})
        errors: list[str] = []

        ibov_return = ifix_return = cdi_return = None
        sp500_return = dolar_retorno = ouro_retorno = selic_retorno = brl_usd = None

        yahoo = YahooFinanceFetcher()
        bcb = BCBFetcher()

        # ---- IBOV via Yahoo (^BVSP) — % acumulado 5 anos ----
        try:
            ibov_data = yahoo.get_historical_price_data(
                ["^BVSP"], period="5y", interval="1d"
            )
            if not ibov_data.empty and "Close" in ibov_data.columns:
                closes = ibov_data["Close"].dropna()
                if len(closes) >= 2:
                    ibov_return = float((closes.iloc[-1] / closes.iloc[0]) - 1)
        except Exception as e:
            logger.error(f"Falha ao buscar IBOV: {e}\n{traceback.format_exc()}")
            errors.append(f"IBOV: {e}")

        # ---- IFIX via Yahoo (IFIX.SA) — % acumulado 5 anos ----
        try:
            ifix_data = yahoo.get_historical_price_data(
                ["IFIX.SA"], period="5y", interval="1d"
            )
            if not ifix_data.empty and "Close" in ifix_data.columns:
                closes = ifix_data["Close"].dropna()
                if len(closes) >= 2:
                    ifix_return = float((closes.iloc[-1] / closes.iloc[0]) - 1)
        except Exception as e:
            logger.error(f"Falha ao buscar IFIX: {e}\n{traceback.format_exc()}")
            errors.append(f"IFIX: {e}")

        # ---- CDI acumulado via BCB (SGS 12) — composição de taxas % a.d. ----
        try:
            cdi_df = bcb.get_cdi(period_days=5 * 365)
            if not cdi_df.empty:
                daily_rates = cdi_df["valor"] / 100
                cdi_return = float((1 + daily_rates).prod() - 1)
        except Exception as e:
            logger.error(f"Falha ao buscar CDI: {e}\n{traceback.format_exc()}")
            errors.append(f"CDI: {e}")

        # ---- S&P 500 via Yahoo (^GSPC) — % acumulado 5 anos em USD ----
        try:
            sp500_data = yahoo.get_historical_price_data(
                ["^GSPC"], period="5y", interval="1d"
            )
            if not sp500_data.empty and "Close" in sp500_data.columns:
                closes = sp500_data["Close"].dropna()
                if len(closes) >= 2:
                    sp500_return = float((closes.iloc[-1] / closes.iloc[0]) - 1)
        except Exception as e:
            logger.error(f"Falha ao buscar S&P 500: {e}\n{traceback.format_exc()}")
            errors.append(f"S&P500: {e}")

        # ---- Dólar (BRL=X via Yahoo) — variação USD/BRL 5 anos ----
        # BRL=X = preço de 1 USD em BRL. Se subiu, dólar valorizou vs BRL.
        try:
            dolar_data = yahoo.get_historical_price_data(
                ["BRL=X"], period="5y", interval="1d"
            )
            if not dolar_data.empty and "Close" in dolar_data.columns:
                closes = dolar_data["Close"].dropna()
                if len(closes) >= 2:
                    dolar_retorno = float((closes.iloc[-1] / closes.iloc[0]) - 1)
        except Exception as e:
            logger.error(f"Falha ao buscar Dólar: {e}\n{traceback.format_exc()}")
            errors.append(f"Dólar: {e}")

        # ---- Ouro via Yahoo (GC=F — Gold Futures) — % acumulado 5 anos em USD ----
        try:
            ouro_data = yahoo.get_historical_price_data(
                ["GC=F"], period="5y", interval="1d"
            )
            if not ouro_data.empty and "Close" in ouro_data.columns:
                closes = ouro_data["Close"].dropna()
                if len(closes) >= 2:
                    ouro_retorno = float((closes.iloc[-1] / closes.iloc[0]) - 1)
        except Exception as e:
            logger.error(f"Falha ao buscar Ouro: {e}\n{traceback.format_exc()}")
            errors.append(f"Ouro: {e}")

        # ---- Selic acumulada via BCB (SGS 432 — meta % a.a.) ----
        # SGS 432 retorna meta Selic apenas nas datas de reunião COPOM (~8×/ano).
        # Precisamos forward-fill para cada dia útil e então compor diariamente.
        try:
            import pandas as pd

            selic_df = bcb.get_selic(period_days=5 * 365)
            if not selic_df.empty:
                selic_ts = selic_df.copy()
                selic_ts["data"] = pd.to_datetime(selic_ts["data"])
                selic_ts = selic_ts.set_index("data").sort_index()
                # Forward-fill meta para cada dia útil (B = business day)
                selic_daily = selic_ts.resample("B").ffill().dropna()
                # Meta % a.a. → fator diário: (1 + r_aa/100)^(1/252)
                selic_daily["fator"] = (1 + selic_daily["valor"] / 100) ** (1 / 252)
                selic_retorno = float(selic_daily["fator"].prod() - 1)
        except Exception as e:
            logger.error(
                f"Falha ao buscar Selic acumulada: {e}\n{traceback.format_exc()}"
            )
            errors.append(f"Selic: {e}")

        # ---- PTAX compra atual via BCB (SGS 10813 — R$/USD) ----
        try:
            ptax_df = bcb.get_ptax(period_days=7)
            if not ptax_df.empty:
                brl_usd = float(ptax_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar PTAX: {e}\n{traceback.format_exc()}")
            errors.append(f"PTAX: {e}")

        if errors:
            ctx["_errors"]["analyze_market.partial"] = "; ".join(errors)

        return MarketMetrics(
            ibov_return=ibov_return,
            ifix_return=ifix_return,
            cdi_return=cdi_return,
            sp500_return=sp500_return,
            dolar_retorno=dolar_retorno,
            ouro_retorno=ouro_retorno,
            selic_retorno=selic_retorno,
            brl_usd=brl_usd,
        )
