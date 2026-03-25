"""Data Lake — persistência temporal de séries financeiras.

Módulo responsável pelo armazenamento e consulta de dados históricos
em SQLite, com exportação para Parquet para pipelines de ML.
"""

from carteira_auto.data.lake.base import DataLake
from carteira_auto.data.lake.fundamentals_lake import FundamentalsLake
from carteira_auto.data.lake.macro_lake import MacroLake
from carteira_auto.data.lake.news_lake import NewsLake
from carteira_auto.data.lake.price_lake import PriceLake

__all__ = [
    "DataLake",
    "PriceLake",
    "MacroLake",
    "FundamentalsLake",
    "NewsLake",
]
