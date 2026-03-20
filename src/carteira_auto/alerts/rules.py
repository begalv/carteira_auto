"""Regras de alerta pré-definidas."""

from carteira_auto.alerts.engine import AlertRule


def rebalance_alert(threshold: float = 0.05) -> AlertRule:
    """Alerta quando desvio de alocação excede threshold."""
    return AlertRule(
        name="rebalance_deviation",
        condition="deviation_above",
        threshold=threshold,
        severity="warning",
        message_template=(
            "Classe {classe} com desvio de {deviation:.1%} "
            "(atual={current:.1%}, meta={target:.1%})"
        ),
    )


def price_drop_alert(threshold: float = 0.10) -> AlertRule:
    """Alerta quando preço cai mais que threshold vs preço médio."""
    return AlertRule(
        name="price_drop",
        condition="price_drop",
        threshold=threshold,
        severity="warning",
        message_template=(
            "{ticker} caiu {drop:.1%} vs preço médio "
            "(atual=R${preco_atual:.2f}, médio=R${preco_medio:.2f})"
        ),
    )


def selic_change_alert(threshold: float = 0.25) -> AlertRule:
    """Alerta quando Selic muda mais que threshold pontos."""
    return AlertRule(
        name="selic_change",
        condition="indicator_change",
        threshold=threshold,
        severity="info",
        message_template="Selic mudou em {change:+.2f} p.p.",
    )
