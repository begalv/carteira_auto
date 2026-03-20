"""Engine de alertas — channel-agnostic."""

from .engine import Alert, AlertEngine, AlertRule

__all__ = ["AlertRule", "Alert", "AlertEngine"]
