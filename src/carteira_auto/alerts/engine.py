"""Alert Engine — avalia regras e emite alertas."""

from datetime import datetime

from pydantic import BaseModel

from carteira_auto.utils import get_logger

logger = get_logger(__name__)


class AlertRule(BaseModel):
    """Regra de alerta."""

    name: str
    condition: str  # "deviation_above", "price_drop", "indicator_change"
    threshold: float
    severity: str = "info"  # "info", "warning", "critical"
    message_template: str = ""


class Alert(BaseModel):
    """Alerta disparado."""

    rule: AlertRule
    triggered_at: datetime
    value: float
    message: str


class AlertEngine:
    """Engine que avalia regras e gera alertas.

    Usage:
        engine = AlertEngine()
        engine.register_rule(AlertRule(
            name="rebalance",
            condition="deviation_above",
            threshold=0.05,
            severity="warning",
            message_template="Classe {classe} com desvio de {deviation:.1%}"
        ))
        alerts = engine.evaluate(ctx)
    """

    def __init__(self):
        self._rules: list[AlertRule] = []

    def register_rule(self, rule: AlertRule) -> None:
        """Registra uma regra de alerta."""
        self._rules.append(rule)
        logger.debug(f"Regra registrada: {rule.name}")

    def register_many(self, rules: list[AlertRule]) -> None:
        """Registra múltiplas regras."""
        for rule in rules:
            self.register_rule(rule)

    def evaluate(self, ctx: dict) -> list[Alert]:
        """Avalia todas as regras contra o contexto.

        Args:
            ctx: PipelineContext com dados dos analyzers.

        Returns:
            Lista de alertas disparados.
        """
        alerts = []

        for rule in self._rules:
            try:
                new_alerts = self._evaluate_rule(rule, ctx)
                alerts.extend(new_alerts)
            except Exception as e:
                logger.warning(f"Erro ao avaliar regra '{rule.name}': {e}")

        if alerts:
            logger.info(f"{len(alerts)} alerta(s) disparado(s)")
        return alerts

    def _evaluate_rule(self, rule: AlertRule, ctx: dict) -> list[Alert]:
        """Avalia uma regra específica."""
        if rule.condition == "deviation_above":
            return self._check_deviation(rule, ctx)
        if rule.condition == "price_drop":
            return self._check_price_drop(rule, ctx)
        if rule.condition == "indicator_change":
            return self._check_indicator_change(rule, ctx)

        logger.warning(f"Condição desconhecida: {rule.condition}")
        return []

    def _check_deviation(self, rule: AlertRule, ctx: dict) -> list[Alert]:
        """Verifica desvios de alocação acima do threshold."""
        metrics = ctx.get("portfolio_metrics")
        if not metrics:
            return []

        alerts = []
        for alloc in metrics.allocations:
            if abs(alloc.deviation) > rule.threshold:
                msg = rule.message_template.format(
                    classe=alloc.asset_class,
                    deviation=alloc.deviation,
                    current=alloc.current_pct,
                    target=alloc.target_pct,
                )
                alerts.append(
                    Alert(
                        rule=rule,
                        triggered_at=datetime.now(),
                        value=alloc.deviation,
                        message=msg,
                    )
                )
        return alerts

    def _check_price_drop(self, rule: AlertRule, ctx: dict) -> list[Alert]:
        """Verifica quedas de preço significativas."""
        portfolio = ctx.get("portfolio")
        if not portfolio:
            return []

        alerts = []
        for asset in portfolio.assets:
            if asset.preco_atual and asset.preco_medio and asset.preco_medio > 0:
                drop = (asset.preco_atual - asset.preco_medio) / asset.preco_medio
                if drop < -rule.threshold:
                    msg = rule.message_template.format(
                        ticker=asset.ticker,
                        drop=drop,
                        preco_atual=asset.preco_atual,
                        preco_medio=asset.preco_medio,
                    )
                    alerts.append(
                        Alert(
                            rule=rule,
                            triggered_at=datetime.now(),
                            value=drop,
                            message=msg,
                        )
                    )
        return alerts

    def _check_indicator_change(self, rule: AlertRule, ctx: dict) -> list[Alert]:
        """Verifica mudanças em indicadores macro."""
        macro = ctx.get("macro_context")
        if not macro:
            return []

        # Genérico — verifica se algum campo mudou significativamente
        # A implementação completa dependeria de comparação com snapshot anterior
        return []
