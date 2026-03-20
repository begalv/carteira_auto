"""Nodes do pipeline de portfolio (load, fetch prices, export)."""

from pathlib import Path
from typing import Optional

from carteira_auto.config import settings
from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


class LoadPortfolioNode(Node):
    """Carrega a carteira a partir da planilha Excel.

    Produz no contexto:
        - "portfolio": Portfolio
        - "source_path": Path
    """

    name = "load_portfolio"
    dependencies: list[str] = []

    def __init__(self, source_path: Optional[Path] = None):
        self._source_path = source_path or settings.paths.PORTFOLIO_FILE

    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.loaders import PortfolioLoader

        loader = PortfolioLoader(self._source_path)
        portfolio = loader.load_portfolio()

        ctx["portfolio"] = portfolio
        ctx["source_path"] = self._source_path
        logger.info(f"Carteira carregada: {len(portfolio.assets)} ativos")
        return ctx


class FetchPricesNode(Node):
    """Busca preços atuais via Yahoo Finance e atualiza o portfolio.

    Lê do contexto:
        - "portfolio": Portfolio

    Produz no contexto:
        - "portfolio": Portfolio (com preços atualizados)
        - "prices": dict[str, float | None]
    """

    name = "fetch_prices"
    dependencies = ["load_portfolio"]

    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.fetchers import YahooFinanceFetcher

        portfolio = ctx["portfolio"]
        fetcher = YahooFinanceFetcher()
        tickers = [a.ticker for a in portfolio.assets]

        # Busca em lote — filtragem e normalização são internas ao fetcher
        prices = fetcher.get_multiple_prices(tickers)

        # Atualiza preços no portfolio
        updated = 0
        for asset in portfolio.assets:
            price = prices.get(asset.ticker)
            if price is not None:
                asset.preco_atual = price
                updated += 1

        ctx["portfolio"] = portfolio
        ctx["prices"] = prices
        logger.info(f"Preços atualizados: {updated}/{len(tickers)} ativos")
        return ctx


class ExportPortfolioPricesNode(Node):
    """Exporta o portfolio com preços atualizados para Excel.

    Lê do contexto:
        - "portfolio": Portfolio
        - "source_path": Path

    Produz no contexto:
        - "output_path": Path
    """

    name = "export_portfolio_prices"
    dependencies = ["fetch_prices"]

    def __init__(self, output_path: Optional[Path] = None):
        self._output_path = output_path or settings.paths.get_portfolio_output_path()

    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.exporters import PortfolioPriceExporter

        portfolio = ctx["portfolio"]
        source_path = ctx["source_path"]

        exporter = PortfolioPriceExporter(source_path, self._output_path)
        output = exporter.export_prices(portfolio)

        ctx["output_path"] = output
        logger.info(f"Planilha exportada: {output}")
        return ctx
