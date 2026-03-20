"""Módulo core com modelos de dados, engine DAG e pipelines."""

from .engine import DAGEngine, Node, PipelineContext
from .models import Asset, Portfolio, SoldAsset
from .pipelines import UpdateExcelPricesPipeline

__all__ = [
    # Models
    "Asset",
    "Portfolio",
    "SoldAsset",
    # Engine
    "DAGEngine",
    "Node",
    "PipelineContext",
    # Pipelines (backward compat)
    "UpdateExcelPricesPipeline",
]
