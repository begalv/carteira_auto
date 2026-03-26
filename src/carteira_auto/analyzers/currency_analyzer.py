"""Analyzer de câmbio e carry trade.

Node DAG: name="analyze_currency", deps=[]
Produz: ctx["currency_metrics"] -> CurrencyMetrics
"""

import traceback

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import CurrencyMetrics
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class CurrencyAnalyzer(Node):
    """Analisa câmbio USD/BRL, DXY, carry trade e taxa real efetiva.

    Não depende de outros nodes — busca dados diretamente dos fetchers.
    Falhas parciais são registradas em ctx["_errors"] mas não impedem
    o retorno dos indicadores obtidos com sucesso.

    Produz no contexto:
        - "currency_metrics": CurrencyMetrics
    """

    name = "analyze_currency"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        metrics = self._build_currency_metrics(ctx)
        ctx["currency_metrics"] = metrics
        logger.info(
            f"Câmbio: USD/BRL={metrics.usd_brl}, DXY={metrics.dxy}, "
            f"carry={metrics.carry_spread}pp"
            if metrics.usd_brl is not None
            else f"Câmbio: {metrics.summary}"
        )
        return ctx

    def _build_currency_metrics(self, ctx: PipelineContext) -> CurrencyMetrics:
        """Busca indicadores de câmbio e calcula métricas."""
        from carteira_auto.data.fetchers import BCBFetcher, FREDFetcher
        from carteira_auto.data.fetchers.yahoo_fetcher import YahooFinanceFetcher

        ctx.setdefault("_errors", {})
        errors: list[str] = []

        usd_brl = usd_brl_ptax_venda = None
        usd_brl_change_1m = usd_brl_change_3m = usd_brl_change_12m = None
        dxy = dxy_change_1m = None
        selic_rate = fed_funds_rate = carry_spread = None
        taxa_cambio_real_efetiva = None

        bcb = BCBFetcher()

        # ---- PTAX compra: corrente + variações 1m/3m/12m ----
        try:
            ptax_df = bcb.get_ptax(period_days=400)
            if not ptax_df.empty:
                usd_brl = float(ptax_df["valor"].iloc[-1])
                usd_brl_change_1m = self._pct_change(ptax_df["valor"], 21)
                usd_brl_change_3m = self._pct_change(ptax_df["valor"], 63)
                usd_brl_change_12m = self._pct_change(ptax_df["valor"], 252)
        except Exception as e:
            logger.error(f"Falha ao buscar PTAX compra: {e}\n{traceback.format_exc()}")
            errors.append(f"PTAX compra: {e}")

        # ---- PTAX venda ----
        try:
            ptax_venda_df = bcb.get_ptax_venda(period_days=7)
            if not ptax_venda_df.empty:
                usd_brl_ptax_venda = float(ptax_venda_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar PTAX venda: {e}\n{traceback.format_exc()}")
            errors.append(f"PTAX venda: {e}")

        # ---- DXY (Dollar Index) via Yahoo Finance ----
        try:
            yahoo = YahooFinanceFetcher()
            dxy_data = yahoo.get_historical_price_data("DX-Y.NYB", period="3mo")
            if not dxy_data.empty:
                close = dxy_data["Close"].dropna()
                if not close.empty:
                    dxy = float(close.iloc[-1])
                    dxy_change_1m = self._pct_change(close, 21)
        except Exception as e:
            logger.error(f"Falha ao buscar DXY: {e}\n{traceback.format_exc()}")
            errors.append(f"DXY: {e}")

        # ---- Selic meta ----
        try:
            selic_df = bcb.get_selic(period_days=30)
            if not selic_df.empty:
                selic_rate = float(selic_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar Selic: {e}\n{traceback.format_exc()}")
            errors.append(f"Selic: {e}")

        # ---- Fed Funds Rate via FRED ----
        try:
            fred = FREDFetcher()
            dff_df = fred.get_series("DFF")
            if not dff_df.empty:
                fed_funds_rate = float(dff_df["value"].iloc[-1])
        except Exception as e:
            logger.error(
                f"Falha ao buscar Fed Funds Rate: {e}\n{traceback.format_exc()}"
            )
            errors.append(f"Fed Funds: {e}")

        # ---- Carry trade spread ----
        if selic_rate is not None and fed_funds_rate is not None:
            carry_spread = round(selic_rate - fed_funds_rate, 2)

        # ---- Taxa de câmbio real efetiva (BCB 11752) ----
        try:
            from datetime import date, timedelta

            cambio_real_df = bcb.get_indicator(
                11752,
                start_date=date.today() - timedelta(days=60),
            )
            if not cambio_real_df.empty:
                taxa_cambio_real_efetiva = float(cambio_real_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(
                f"Falha ao buscar câmbio real efetivo: {e}\n{traceback.format_exc()}"
            )
            errors.append(f"Câmbio real: {e}")

        if errors:
            ctx["_errors"]["analyze_currency.partial"] = "; ".join(errors)

        summary = self._generate_summary(
            usd_brl, dxy, carry_spread, taxa_cambio_real_efetiva
        )

        return CurrencyMetrics(
            usd_brl=usd_brl,
            usd_brl_ptax_venda=usd_brl_ptax_venda,
            usd_brl_change_1m=usd_brl_change_1m,
            usd_brl_change_3m=usd_brl_change_3m,
            usd_brl_change_12m=usd_brl_change_12m,
            dxy=dxy,
            dxy_change_1m=dxy_change_1m,
            selic_rate=selic_rate,
            fed_funds_rate=fed_funds_rate,
            carry_spread=carry_spread,
            taxa_cambio_real_efetiva=taxa_cambio_real_efetiva,
            summary=summary,
        )

    @staticmethod
    def _pct_change(series, lookback: int) -> float | None:
        """Calcula variação percentual vs N períodos atrás."""
        if len(series) <= lookback:
            return None
        current = float(series.iloc[-1])
        past = float(series.iloc[-lookback - 1])
        if past == 0:
            return None
        return round((current - past) / past * 100, 2)

    @staticmethod
    def _generate_summary(
        usd_brl: float | None,
        dxy: float | None,
        carry: float | None,
        cambio_real: float | None,
    ) -> str:
        """Gera sumário textual do cenário cambial."""
        parts = []
        if usd_brl is not None:
            parts.append(f"USD/BRL R${usd_brl:.2f}")
        if dxy is not None:
            parts.append(f"DXY {dxy:.1f}")
        if carry is not None:
            parts.append(f"carry {carry:+.2f}pp")
        if cambio_real is not None:
            parts.append(f"câmbio real {cambio_real:.1f}")
        return "; ".join(parts) if parts else "Dados cambiais indisponíveis"
