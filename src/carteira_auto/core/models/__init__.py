"""Modelos de dados — re-exporta tudo para backward compatibility.

Usage:
    from carteira_auto.core.models import Portfolio, Asset, SoldAsset
    from carteira_auto.core.models import PortfolioMetrics, RiskMetrics
    from carteira_auto.core.models import MacroIndicator, MacroSnapshot
"""

from carteira_auto.core.models.analysis import (
    AllocationResult,
    MacroContext,
    MarketMetrics,
    PortfolioMetrics,
    RebalanceRecommendation,
    RiskMetrics,
)
from carteira_auto.core.models.economic import (
    EconomicSectorIndicator,
    MacroIndicator,
    MacroSnapshot,
    MarketIndicator,
    MarketSnapshot,
    SectorIndicator,
)
from carteira_auto.core.models.portfolio import Asset, Portfolio, SoldAsset

__all__ = [
    # Portfolio
    "Asset",
    "SoldAsset",
    "Portfolio",
    # Analysis
    "AllocationResult",
    "PortfolioMetrics",
    "RiskMetrics",
    "MarketMetrics",
    "MacroContext",
    "RebalanceRecommendation",
    # Economic
    "MacroIndicator",
    "MacroSnapshot",
    "MarketIndicator",
    "MarketSnapshot",
    "SectorIndicator",
    "EconomicSectorIndicator",
]
