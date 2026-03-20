"""Nodes de alertas — avaliação de regras contra dados do pipeline."""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


class EvaluateAlertsNode(Node):
    """Avalia regras de alerta contra o contexto do pipeline.

    Lê do contexto (opcionais):
        - "portfolio": Portfolio
        - "portfolio_metrics": PortfolioMetrics
        - "macro_context": MacroContext

    Produz no contexto:
        - "alerts": list[Alert]
    """

    name = "evaluate_alerts"
    dependencies: list[str] = []

    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.alerts import AlertEngine
        from carteira_auto.alerts.channels import ConsoleChannel, LogChannel
        from carteira_auto.alerts.rules import price_drop_alert, rebalance_alert

        # Cria alert engine com regras padrão
        alert_engine = AlertEngine()
        alert_engine.register_many(
            [
                rebalance_alert(threshold=0.05),
                price_drop_alert(threshold=0.10),
            ]
        )

        # Avalia
        alerts = alert_engine.evaluate(ctx)
        ctx["alerts"] = alerts

        # Emite via canais
        if alerts:
            console = ConsoleChannel()
            log_channel = LogChannel()
            console.send_many(alerts)
            log_channel.send_many(alerts)

        return ctx
