"""Analyzer de rebalanceamento — recomendações de compra/venda.

Node DAG: name="rebalance", deps=["analyze_portfolio"]
Produz: ctx["rebalance_recommendations"] -> list[RebalanceRecommendation]
"""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import (
    Portfolio,
    PortfolioMetrics,
    RebalanceRecommendation,
)
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class Rebalancer(Node):
    """Gera recomendações de rebalanceamento.

    Lê do contexto:
        - "portfolio": Portfolio
        - "portfolio_metrics": PortfolioMetrics

    Produz no contexto:
        - "rebalance_recommendations": list[RebalanceRecommendation]
    """

    name = "rebalance"
    dependencies = ["analyze_portfolio"]

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        portfolio: Portfolio = ctx["portfolio"]
        metrics: PortfolioMetrics = ctx["portfolio_metrics"]
        recommendations = self._generate_recommendations(portfolio, metrics, ctx)
        ctx["rebalance_recommendations"] = recommendations

        if recommendations:
            logger.info(f"Rebalanceamento: {len(recommendations)} recomendações")
        else:
            logger.info("Carteira equilibrada — sem recomendações")
        return ctx

    def _generate_recommendations(
        self, portfolio: Portfolio, metrics: PortfolioMetrics, ctx: PipelineContext
    ) -> list[RebalanceRecommendation]:
        """Gera recomendações baseadas nos desvios de alocação.

        Parâmetros via PipelineContext:
            - ctx["target_allocations"]: dict[str, float] — metas por classe
            - ctx["rebalance_threshold"]: float — tolerância de desvio (default 0.05)
            - ctx["min_trade_value"]: float — valor mínimo por operação (default 100)
        """
        targets: dict[str, float] = ctx.get("target_allocations", {})
        threshold: float = ctx.get("rebalance_threshold", 0.05)
        min_trade: float = ctx.get("min_trade_value", 100.0)
        total_value = metrics.total_value

        if not targets:
            logger.warning(
                "target_allocations não fornecido no contexto — "
                "rebalanceamento ignorado"
            )
            return []

        if total_value <= 0:
            return []

        recommendations = []

        # Agrupa ativos por classe
        class_assets: dict[str, list] = {}
        for asset in portfolio.assets:
            classe = asset.classe or "Outros"
            class_assets.setdefault(classe, []).append(asset)

        for allocation in metrics.allocations:
            if abs(allocation.deviation) < threshold:
                continue

            classe = allocation.asset_class
            if classe not in targets:
                continue

            target_value = allocation.target_pct * total_value
            current_value = allocation.current_pct * total_value
            diff = target_value - current_value

            if abs(diff) < min_trade:
                continue

            # Distribui entre ativos da classe
            assets_in_class = class_assets.get(classe, [])
            if not assets_in_class:
                continue

            if diff > 0:
                recs = self._distribute_buy(assets_in_class, diff, min_trade)
            else:
                recs = self._distribute_sell(assets_in_class, abs(diff), min_trade)

            recommendations.extend(recs)

        return recommendations

    def _distribute_buy(
        self, assets: list, total_to_buy: float, min_trade: float = 100.0
    ) -> list[RebalanceRecommendation]:
        """Distribui compra entre ativos da classe."""
        total_meta = sum(a.pct_meta or 0 for a in assets)
        if total_meta <= 0:
            total_meta = len(assets)
            weights = {a.ticker: 1 / total_meta for a in assets}
        else:
            weights = {a.ticker: (a.pct_meta or 0) / total_meta for a in assets}

        recs = []
        for asset in assets:
            value = total_to_buy * weights.get(asset.ticker, 0)
            if value < min_trade:
                continue

            quantity = None
            if asset.preco_atual and asset.preco_atual > 0:
                quantity = value / asset.preco_atual

            recs.append(
                RebalanceRecommendation(
                    ticker=asset.ticker,
                    action="comprar",
                    quantity=quantity,
                    value=value,
                    reason=f"Classe {asset.classe} abaixo da meta",
                )
            )
        return recs

    def _distribute_sell(
        self, assets: list, total_to_sell: float, min_trade: float = 100.0
    ) -> list[RebalanceRecommendation]:
        """Distribui venda entre ativos da classe."""
        total_pos = sum(a.posicao_atual or 0 for a in assets)
        if total_pos <= 0:
            return []

        recs = []
        for asset in assets:
            weight = (asset.posicao_atual or 0) / total_pos
            value = total_to_sell * weight
            if value < min_trade:
                continue

            quantity = None
            if asset.preco_atual and asset.preco_atual > 0:
                quantity = value / asset.preco_atual

            recs.append(
                RebalanceRecommendation(
                    ticker=asset.ticker,
                    action="vender",
                    quantity=quantity,
                    value=value,
                    reason=f"Classe {asset.classe} acima da meta",
                )
            )
        return recs
