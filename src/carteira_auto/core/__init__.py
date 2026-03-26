"""Módulo core com modelos de dados, engine DAG, pipelines e Result type."""

from .engine import DAGEngine, Node, PipelineContext
from .models import Asset, Portfolio, SoldAsset
from .pipelines import UpdateExcelPricesPipeline
from .result import Err, Ok, Result

__all__ = [
    # Models
    "Asset",
    "Portfolio",
    "SoldAsset",
    # Engine
    "DAGEngine",
    "Node",
    "PipelineContext",
    # Result
    "Ok",
    "Err",
    "Result",
    # Pipelines (backward compat)
    "UpdateExcelPricesPipeline",
]
