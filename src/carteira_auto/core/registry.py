"""Registry de pipelines — mapeia nomes CLI para nodes terminais do DAG."""

from __future__ import annotations

from pathlib import Path

from carteira_auto.core.engine import DAGEngine
from carteira_auto.core.nodes.portfolio_nodes import (
    ExportPortfolioPricesNode,
    FetchPricesNode,
    LoadPortfolioNode,
)
from carteira_auto.utils import get_logger

logger = get_logger(__name__)

# Mapeamento: nome CLI → node terminal
PIPELINE_PRESETS: dict[str, str] = {
    "update-excel-portfolio-prices": "export_portfolio_prices",
}


def create_engine(
    source_path: Path | None = None,
    output_path: Path | None = None,
) -> DAGEngine:
    """Cria um DAGEngine com todos os nodes registrados.

    Args:
        source_path: Path customizado da planilha de origem.
        output_path: Path customizado da planilha de saída.

    Returns:
        Engine pronto para executar pipelines.
    """
    engine = DAGEngine()

    # Nodes de portfolio
    engine.register_many(
        [
            LoadPortfolioNode(source_path=source_path),
            FetchPricesNode(),
            ExportPortfolioPricesNode(output_path=output_path),
        ]
    )

    return engine


def get_terminal_node(pipeline_name: str) -> str:
    """Retorna o node terminal para um nome de pipeline.

    Args:
        pipeline_name: Nome do pipeline (como usado no CLI).

    Returns:
        Nome do node terminal.

    Raises:
        KeyError: Pipeline não encontrado.
    """
    if pipeline_name not in PIPELINE_PRESETS:
        available = ", ".join(sorted(PIPELINE_PRESETS.keys()))
        raise KeyError(
            f"Pipeline '{pipeline_name}' não encontrado. " f"Disponíveis: {available}"
        )
    return PIPELINE_PRESETS[pipeline_name]


def list_pipelines() -> dict[str, str]:
    """Lista todos os pipelines disponíveis.

    Returns:
        Dict de {nome_cli: node_terminal}.
    """
    return dict(PIPELINE_PRESETS)
