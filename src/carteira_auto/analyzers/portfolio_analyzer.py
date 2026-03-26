"""Analyzer de portfolio — métricas consolidadas da carteira.

Node DAG: name="analyze_portfolio", deps=["fetch_portfolio_prices"]
Produz: ctx["portfolio_metrics"] -> PortfolioMetrics
"""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import AllocationResult, Portfolio, PortfolioMetrics
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)

# Threshold padrão para classificar ação (comprar/manter/vender)
_DEFAULT_REBALANCE_THRESHOLD = 0.05


class PortfolioAnalyzer(Node):
    """Calcula métricas consolidadas da carteira.

    Lê do contexto:
        - "portfolio": Portfolio (com preços atualizados)

    Produz no contexto:
        - "portfolio_metrics": PortfolioMetrics
    """

    name = "analyze_portfolio"
    dependencies = ["fetch_portfolio_prices"]

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        portfolio: Portfolio = ctx["portfolio"]
        metrics = self._calculate_metrics(portfolio, ctx)
        ctx["portfolio_metrics"] = metrics
        logger.info(
            f"Portfolio: valor={metrics.total_value:,.2f}, "
            f"retorno={metrics.total_return_pct:.2%}"
        )
        return ctx

    def _calculate_metrics(
        self, portfolio: Portfolio, ctx: PipelineContext
    ) -> PortfolioMetrics:
        """Calcula métricas consolidadas."""
        assets = portfolio.assets

        # Totais
        total_value = sum(a.posicao_atual or 0 for a in assets)
        total_cost = sum(a.preco_posicao or 0 for a in assets)
        total_return = total_value - total_cost
        total_return_pct = (total_return / total_cost) if total_cost > 0 else 0

        # Dividend yield (proventos / posição)
        total_dividends = sum(a.proventos_recebidos or 0 for a in assets)
        dividend_yield = (total_dividends / total_value) if total_value > 0 else 0

        # Alocação por classe
        allocations = self._calculate_allocations(assets, total_value, ctx)

        return PortfolioMetrics(
            total_value=total_value,
            total_cost=total_cost,
            total_return=total_return,
            total_return_pct=total_return_pct,
            dividend_yield=dividend_yield,
            allocations=allocations,
        )

    def _calculate_allocations(
        self, assets: list, total_value: float, ctx: PipelineContext
    ) -> list[AllocationResult]:
        """Calcula alocação atual vs meta por classe de ativo.

        Parâmetros via PipelineContext:
            - ctx["target_allocations"]: dict[str, float] — metas por classe
            - ctx["rebalance_threshold"]: float — tolerância de desvio
        """
        targets: dict[str, float] = ctx.get("target_allocations", {})
        threshold: float = ctx.get("rebalance_threshold", _DEFAULT_REBALANCE_THRESHOLD)

        if not targets:
            logger.warning(
                "target_allocations não fornecido no contexto — "
                "alocação calculada sem metas"
            )
            return []

        # Agrupa valor por classe
        class_values: dict[str, float] = {}
        for asset in assets:
            classe = asset.classe or "Outros"
            class_values[classe] = class_values.get(classe, 0) + (
                asset.posicao_atual or 0
            )

        results = []
        for classe, target_pct in targets.items():
            current_value = class_values.get(classe, 0)
            current_pct = (current_value / total_value) if total_value > 0 else 0
            deviation = current_pct - target_pct

            # Determina ação
            if deviation > threshold:
                action = "vender"
            elif deviation < -threshold:
                action = "comprar"
            else:
                action = "manter"

            results.append(
                AllocationResult(
                    asset_class=classe,
                    current_pct=current_pct,
                    target_pct=target_pct,
                    deviation=deviation,
                    action=action,
                )
            )

        return results
