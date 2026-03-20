"""Nodes de storage — persistência de snapshots."""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


class SaveSnapshotNode(Node):
    """Persiste métricas do pipeline em JSON para consulta futura.

    Lê do contexto (opcionais — salva o que existir):
        - "portfolio_metrics": PortfolioMetrics
        - "macro_context": MacroContext
        - "market_metrics": MarketMetrics
        - "risk_metrics": RiskMetrics

    Produz no contexto:
        - "snapshot_path": Path
    """

    name = "save_snapshot"
    dependencies: list[str] = []

    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.storage import SnapshotStore

        store = SnapshotStore()

        # Coleta métricas disponíveis
        data = {}

        if "portfolio_metrics" in ctx:
            m = ctx["portfolio_metrics"]
            data["total_value"] = m.total_value
            data["total_cost"] = m.total_cost
            data["total_return"] = m.total_return
            data["total_return_pct"] = m.total_return_pct
            data["dividend_yield"] = m.dividend_yield
            data["allocations"] = {
                a.asset_class: {
                    "current_pct": a.current_pct,
                    "target_pct": a.target_pct,
                    "deviation": a.deviation,
                }
                for a in m.allocations
            }

        if "macro_context" in ctx:
            mc = ctx["macro_context"]
            data["macro"] = {
                "selic": mc.selic,
                "ipca": mc.ipca,
                "cambio": mc.cambio,
                "pib_growth": mc.pib_growth,
            }

        if "market_metrics" in ctx:
            mm = ctx["market_metrics"]
            data["market"] = {
                "ibov_return": mm.ibov_return,
                "ifix_return": mm.ifix_return,
                "cdi_return": mm.cdi_return,
            }

        if "risk_metrics" in ctx:
            r = ctx["risk_metrics"]
            data["risk"] = {
                "volatility": r.volatility,
                "var_95": r.var_95,
                "var_99": r.var_99,
                "sharpe_ratio": r.sharpe_ratio,
                "max_drawdown": r.max_drawdown,
                "beta": r.beta,
            }

        if not data:
            logger.warning("Nenhuma métrica disponível para salvar no snapshot")
            return ctx

        filepath = store.save_metadata(data)
        ctx["snapshot_path"] = filepath
        return ctx
