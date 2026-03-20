"""Analyzer de setores econômicos — dados IBGE/BCB sobre economia real.

Node DAG: name="analyze_economic_sectors", deps=[]
Produz: ctx["economic_sectors"] -> list[EconomicSectorIndicator]
"""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import EconomicSectorIndicator
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class EconomicSectorAnalyzer(Node):
    """Analisa setores da economia real via dados IBGE.

    Não depende de outros nodes — busca dados diretamente.

    Produz no contexto:
        - "economic_sectors": list[EconomicSectorIndicator]
    """

    name = "analyze_economic_sectors"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        sectors = self._fetch_economic_data()
        ctx["economic_sectors"] = sectors
        logger.info(f"Setores econômicos: {len(sectors)} setores analisados")
        return ctx

    def _fetch_economic_data(self) -> list[EconomicSectorIndicator]:
        """Busca dados setoriais do IBGE."""
        from carteira_auto.data.fetchers import IBGEFetcher

        sectors = []

        try:
            ibge = IBGEFetcher()
            pib_df = ibge.get_pib(quarters=4)

            if not pib_df.empty:
                for _, row in pib_df.iterrows():
                    sectors.append(
                        EconomicSectorIndicator(
                            sector=row.get("variavel", "PIB"),
                            growth_rate=row.get("valor"),
                            source="ibge",
                        )
                    )
        except Exception as e:
            logger.warning(f"Falha ao buscar dados setoriais IBGE: {e}")

        return sectors
