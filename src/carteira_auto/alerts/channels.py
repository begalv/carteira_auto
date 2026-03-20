"""Canais de notificação para alertas.

Channel-agnostic: cada canal implementa send().
Por ora, apenas ConsoleChannel. Stubs para futuros canais.
"""

from abc import ABC, abstractmethod

from carteira_auto.alerts.engine import Alert
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


class AlertChannel(ABC):
    """Interface base para canais de alerta."""

    @abstractmethod
    def send(self, alert: Alert) -> None:
        """Envia um alerta pelo canal."""

    def send_many(self, alerts: list[Alert]) -> None:
        """Envia múltiplos alertas."""
        for alert in alerts:
            self.send(alert)


class ConsoleChannel(AlertChannel):
    """Canal de alerta via console (print)."""

    SEVERITY_ICONS = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨",
    }

    def send(self, alert: Alert) -> None:
        """Imprime alerta no console."""
        icon = self.SEVERITY_ICONS.get(alert.rule.severity, "📢")
        print(f"{icon} [{alert.rule.severity.upper()}] {alert.message}")


class LogChannel(AlertChannel):
    """Canal de alerta via logging."""

    def send(self, alert: Alert) -> None:
        """Loga alerta."""
        severity = alert.rule.severity
        msg = f"[ALERTA:{alert.rule.name}] {alert.message}"

        if severity == "critical":
            logger.critical(msg)
        elif severity == "warning":
            logger.warning(msg)
        else:
            logger.info(msg)


# Stubs para canais futuros
# class EmailChannel(AlertChannel): ...
# class TelegramChannel(AlertChannel): ...
# class SlackChannel(AlertChannel): ...
