"""Analyzer de risco — volatilidade, VaR, Sharpe, drawdown, beta.

Node DAG: name="analyze_risk", deps=["fetch_portfolio_prices", "analyze_portfolio"]
Produz: ctx["risk_metrics"] -> RiskMetrics
"""

import traceback

import numpy as np

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import Portfolio, RiskMetrics
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class RiskAnalyzer(Node):
    """Calcula métricas de risco da carteira.

    Lê do contexto:
        - "portfolio": Portfolio

    Produz no contexto:
        - "risk_metrics": RiskMetrics
    """

    name = "analyze_risk"
    dependencies = ["fetch_portfolio_prices", "analyze_portfolio"]

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        portfolio: Portfolio = ctx["portfolio"]
        metrics = self._calculate_risk(portfolio, ctx)
        ctx["risk_metrics"] = metrics
        logger.info(
            f"Risco: vol={metrics.volatility}, "
            f"VaR95={metrics.var_95}, Sharpe={metrics.sharpe_ratio}"
        )
        return ctx

    def _calculate_risk(
        self, portfolio: Portfolio, ctx: PipelineContext
    ) -> RiskMetrics:
        """Calcula métricas de risco via dados históricos."""
        from carteira_auto.data.fetchers import YahooFinanceFetcher

        tickers = [
            a.ticker
            for a in portfolio.assets
            if a.ticker and a.posicao_atual and a.posicao_atual > 0
        ]

        if not tickers:
            return RiskMetrics()

        try:
            yahoo = YahooFinanceFetcher()
            hist = yahoo.get_historical_price_data(tickers, period="5y", interval="1d")

            if hist.empty:
                return RiskMetrics()

            returns = hist.pct_change().dropna()

            if returns.empty or len(returns) < 20:
                return RiskMetrics()

            weights = self._get_weights(portfolio, tickers, returns.columns)
            if weights is None:
                return RiskMetrics()

            portfolio_returns = (returns * weights).sum(axis=1)

            risk_free_daily = self._get_risk_free_daily(ctx)

            volatility = float(portfolio_returns.std() * np.sqrt(252))
            var_95 = float(np.percentile(portfolio_returns, 5))
            var_99 = float(np.percentile(portfolio_returns, 1))
            sharpe = self._sharpe_ratio(portfolio_returns, risk_free_daily)
            max_dd = self._max_drawdown(portfolio_returns)
            beta = self._beta(portfolio_returns)

            return RiskMetrics(
                volatility=volatility,
                var_95=var_95,
                var_99=var_99,
                sharpe_ratio=sharpe,
                max_drawdown=max_dd,
                beta=beta,
            )

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Falha ao calcular risco: {e}\n{tb}")
            ctx.setdefault("_errors", {})
            ctx["_errors"]["analyze_risk._calculate_risk"] = str(e)
            return RiskMetrics()

    def _get_weights(
        self, portfolio: Portfolio, tickers: list, columns
    ) -> np.ndarray | None:
        """Calcula vetor de pesos normalizados por posição atual."""
        total = sum(
            a.posicao_atual or 0 for a in portfolio.assets if a.ticker in tickers
        )
        if total <= 0:
            return None

        # Mapeia ticker → peso
        weight_map = {}
        for asset in portfolio.assets:
            if asset.ticker in tickers:
                weight_map[asset.ticker] = (asset.posicao_atual or 0) / total

        # Alinha com colunas do DataFrame de retornos
        weights = []
        for col in columns:
            # Coluna pode ser ticker ou ticker.SA
            clean = str(col).replace(".SA", "")
            weights.append(weight_map.get(clean, weight_map.get(str(col), 0)))

        arr = np.array(weights)
        if arr.sum() <= 0:
            return None
        return arr / arr.sum()

    def _get_risk_free_daily(self, ctx: PipelineContext) -> float:
        """Obtém taxa livre de risco diária.

        Prioridade:
        1. ctx["risk_free_daily"] — passado explicitamente pelo pipeline
        2. CDI diário mais recente via BCB SGS
        3. Fallback: 0 (sem ajuste de rf)
        """
        # 1. Contexto explícito
        if "risk_free_daily" in ctx:
            return float(ctx["risk_free_daily"])

        # 2. CDI atual via BCB
        try:
            from carteira_auto.data.fetchers import BCBFetcher

            bcb = BCBFetcher()
            cdi = bcb.get_cdi(period_days=5)  # últimos 5 dias úteis
            if not cdi.empty:
                rf = float(cdi["valor"].iloc[-1]) / 100  # % → decimal
                logger.debug(f"Risk-free diário via CDI: {rf:.6f}")
                return rf
        except Exception as e:
            logger.warning(f"Falha ao obter CDI para risk-free: {e}")

        # 3. Fallback
        logger.warning("Risk-free diário não disponível — usando 0")
        return 0.0

    def _sharpe_ratio(self, returns, risk_free_daily: float = 0.0) -> float | None:
        """Sharpe ratio anualizado."""
        excess = returns - risk_free_daily
        if excess.std() == 0:
            return None
        return float((excess.mean() / excess.std()) * np.sqrt(252))

    def _max_drawdown(self, returns) -> float | None:
        """Máximo drawdown da série."""
        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        if drawdown.empty:
            return None
        return float(drawdown.min())

    def _beta(self, portfolio_returns) -> float | None:
        """Beta contra IBOV."""
        from carteira_auto.data.fetchers import YahooFinanceFetcher

        try:
            yahoo = YahooFinanceFetcher()
            ibov = yahoo.get_historical_price_data(
                ["^BVSP"], period="5y", interval="1d"
            )
            if ibov.empty:
                return None

            ibov_returns = ibov.pct_change().dropna()

            # Alinha séries
            if hasattr(ibov_returns, "columns"):
                ibov_returns = ibov_returns.iloc[:, 0]

            common_idx = portfolio_returns.index.intersection(ibov_returns.index)
            if len(common_idx) < 20:
                return None

            p = portfolio_returns.loc[common_idx].values
            m = ibov_returns.loc[common_idx].values

            cov = np.cov(p, m)
            if cov[1, 1] == 0:
                return None
            return float(cov[0, 1] / cov[1, 1])

        except Exception as e:
            logger.warning(f"Falha ao calcular beta: {e}")
            return None
