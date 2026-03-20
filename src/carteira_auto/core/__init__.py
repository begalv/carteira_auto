"""Módulo core com modelos de dados e pipelines."""

from .models import Asset, Portfolio, SoldAsset
from .pipelines import UpdatePricesPipeline

__all__ = [
    "Asset",
    "Portfolio",
    "SoldAsset",
    "UpdatePricesPipeline",
]
