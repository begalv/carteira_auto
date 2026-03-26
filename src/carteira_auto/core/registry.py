"""Registry de pipelines — mapeia nomes CLI para nodes terminais do DAG."""

from __future__ import annotations

from pathlib import Path

from carteira_auto.core.engine import DAGEngine
from carteira_auto.core.nodes.alert_nodes import EvaluateAlertsNode
from carteira_auto.core.nodes.ingest_nodes import (
    IngestFundamentalsNode,
    IngestMacroNode,
    IngestNewsNode,
    IngestPricesNode,
)
from carteira_auto.core.nodes.portfolio_nodes import (
    ExportPortfolioPricesNode,
    FetchPortfolioPricesNode,
    FetchPricesNode,
    LoadPortfolioNode,
)
from carteira_auto.core.nodes.storage_nodes import SaveSnapshotNode
from carteira_auto.utils import get_logger

logger = get_logger(__name__)

# Mapeamento: nome CLI → node terminal
PIPELINE_PRESETS: dict[str, str] = {
    "update-excel-portfolio-prices": "export_portfolio_prices",
    "analyze": "analyze_portfolio",
    "rebalance": "rebalance",
    "risk": "analyze_risk",
    "macro": "analyze_macro",
    "market": "analyze_market",
    "market-sectors": "analyze_market_sectors",
    "economic-sectors": "analyze_economic_sectors",
    "ingest-prices": "ingest_prices",
    "ingest-macro": "ingest_macro",
    "ingest-fundamentals": "ingest_fundamentals",
    "ingest-news": "ingest_news",
    "currency": "analyze_currency",
    "commodities": "analyze_commodities",
    "fiscal": "analyze_fiscal",
}

# Descrições para o CLI
PIPELINE_DESCRIPTIONS: dict[str, str] = {
    "update-excel-portfolio-prices": "Atualiza preços e exporta planilha Excel",
    "analyze": "Analisa métricas da carteira (alocação, retorno)",
    "rebalance": "Gera recomendações de rebalanceamento",
    "risk": "Calcula métricas de risco (VaR, Sharpe, beta)",
    "macro": "Analisa contexto macroeconômico (Selic, IPCA, câmbio, PIB)",
    "market": "Analisa benchmarks de mercado (IBOV, IFIX, CDI)",
    "market-sectors": "Analisa performance por setor de mercado",
    "economic-sectors": "Analisa setores da economia real (IBGE)",
    "ingest-prices": "Ingere preços históricos no DataLake (Yahoo Finance)",
    "ingest-macro": "Ingere indicadores macro no DataLake (BCB, IBGE)",
    "ingest-fundamentals": "Ingere dados fundamentalistas no DataLake (Yahoo Finance)",
    "ingest-news": "Ingere notícias financeiras no DataLake (NewsAPI, RSS)",
    "currency": "Analisa câmbio, DXY, carry trade e taxa real efetiva",
    "commodities": "Analisa preços e ciclo de commodities (petróleo, ouro, agro)",
    "fiscal": "Analisa dívida/PIB, resultado primário e trajetória fiscal",
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
    from carteira_auto.analyzers import (
        CommodityAnalyzer,
        CurrencyAnalyzer,
        EconomicSectorAnalyzer,
        FiscalAnalyzer,
        MacroAnalyzer,
        MarketAnalyzer,
        MarketSectorAnalyzer,
        PortfolioAnalyzer,
        Rebalancer,
        RiskAnalyzer,
    )

    dag_engine = DAGEngine()

    # Nodes de portfolio (core)
    dag_engine.register_many(
        [
            LoadPortfolioNode(source_path=source_path),
            FetchPricesNode(),
            FetchPortfolioPricesNode(),
            ExportPortfolioPricesNode(output_path=output_path),
        ]
    )

    # Analyzers
    dag_engine.register_many(
        [
            PortfolioAnalyzer(),
            MarketAnalyzer(),
            MacroAnalyzer(),
            RiskAnalyzer(),
            Rebalancer(),
            MarketSectorAnalyzer(),
            EconomicSectorAnalyzer(),
            CurrencyAnalyzer(),
            CommodityAnalyzer(),
            FiscalAnalyzer(),
        ]
    )

    # Storage
    dag_engine.register(SaveSnapshotNode())

    # Alertas
    dag_engine.register(EvaluateAlertsNode())

    # Ingestão (DataLake)
    dag_engine.register_many(
        [
            IngestPricesNode(),
            IngestMacroNode(),
            IngestFundamentalsNode(),
            IngestNewsNode(),
        ]
    )

    return dag_engine


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
    """Lista todos os pipelines disponíveis com descrições.

    Returns:
        Dict de {nome_cli: descrição}.
    """
    return dict(PIPELINE_DESCRIPTIONS)
