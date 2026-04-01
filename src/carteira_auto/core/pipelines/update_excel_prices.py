"""Pipeline de atualização de preços da carteira."""

from pathlib import Path

from carteira_auto.config import settings
from carteira_auto.core.models import Portfolio
from carteira_auto.data.exporters import PortfolioPriceExporter
from carteira_auto.data.fetchers import YahooFinanceFetcher
from carteira_auto.data.loaders import PortfolioLoader
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution, timer

logger = get_logger(__name__)


class UpdateExcelPricesPipeline:
    """Pipeline: carrega carteira -> busca preços -> exporta planilha atualizada.

    Usage:
        # Com paths padrão de settings:
        pipeline = UpdateExcelPricesPipeline()
        output = pipeline.run()

        # Com paths customizados:
        pipeline = UpdateExcelPricesPipeline(
            source_path=Path("minha/planilha.xlsx"),
            output_path=Path("saida/atualizada.xlsx"),
        )
        output = pipeline.run()
    """

    def __init__(
        self,
        source_path: Path | None = None,
        output_path: Path | None = None,
    ):
        self.source_path = source_path or settings.paths.PORTFOLIO_FILE
        self.output_path = output_path or settings.paths.get_portfolio_output_path()

    @log_execution
    @timer
    def run(self) -> Path:
        """Executa o pipeline completo.

        Returns:
            Path do arquivo exportado.
        """
        portfolio = self._load()
        portfolio = self._fetch_prices(portfolio)
        return self._export(portfolio)

    def _load(self) -> Portfolio:
        """Carrega a carteira da planilha."""
        loader = PortfolioLoader(self.source_path)
        return loader.load_portfolio()

    def _fetch_prices(self, portfolio: Portfolio) -> Portfolio:
        """Busca preços atuais no Yahoo Finance e atualiza o portfolio."""
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

        logger.info(f"Preços atualizados: {updated}/{len(tickers)} ativos")
        return portfolio

    def _export(self, portfolio: Portfolio) -> Path:
        """Exporta o portfolio com preços atualizados."""
        exporter = PortfolioPriceExporter(self.source_path, self.output_path)
        output = exporter.export_prices(portfolio)
        logger.info(f"Planilha exportada: {output}")
        return output
