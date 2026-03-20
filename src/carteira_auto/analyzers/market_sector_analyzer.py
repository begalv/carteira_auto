"""Analyzer de setores de mercado — performance por setor/indústria.

Node DAG: name="analyze_market_sectors", deps=[]
Produz: ctx["market_sectors"] -> list[SectorIndicator]
"""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import SectorIndicator
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class MarketSectorAnalyzer(Node):
    """Analisa performance de setores do mercado financeiro.

    Não depende de outros nodes — busca dados diretamente via Yahoo.

    Produz no contexto:
        - "market_sectors": list[SectorIndicator]
    """

    name = "analyze_market_sectors"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        sectors = self._fetch_sector_data()
        ctx["market_sectors"] = sectors
        logger.info(f"Setores de mercado: {len(sectors)} setores analisados")
        return ctx

    def _fetch_sector_data(self) -> list[SectorIndicator]:
        """Busca performance dos setores via Yahoo Finance."""
        from carteira_auto.data.fetchers import YahooFinanceFetcher

        sectors = []
        yahoo = YahooFinanceFetcher()

        try:
            summary = yahoo.get_market_summary()
            if summary:
                for item in summary:
                    sectors.append(
                        SectorIndicator(
                            sector=item.get("shortName", "N/A"),
                            ticker=item.get("symbol"),
                            return_pct=item.get("regularMarketChangePercent"),
                            volume=item.get("regularMarketVolume"),
                            market_cap=item.get("marketCap"),
                        )
                    )
        except Exception as e:
            logger.warning(f"Falha ao buscar setores de mercado: {e}")

        return sectors
