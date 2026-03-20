"""Analyzer macroeconômico — indicadores BCB e IBGE.

Node DAG: name="analyze_macro", deps=[]
Produz: ctx["macro_context"] -> MacroContext
"""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import MacroContext
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class MacroAnalyzer(Node):
    """Consolida contexto macroeconômico a partir de BCB e IBGE.

    Não depende de outros nodes — busca dados diretamente.

    Produz no contexto:
        - "macro_context": MacroContext
    """

    name = "analyze_macro"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        macro = self._build_macro_context()
        ctx["macro_context"] = macro
        logger.info(
            f"Macro: Selic={macro.selic}, IPCA={macro.ipca}, "
            f"Câmbio={macro.cambio}, PIB={macro.pib_growth}"
        )
        return ctx

    def _build_macro_context(self) -> MacroContext:
        """Busca indicadores e consolida contexto macro."""
        from carteira_auto.data.fetchers import BCBFetcher, IBGEFetcher

        selic = None
        ipca = None
        cambio = None
        pib_growth = None

        # Selic via BCB
        try:
            bcb = BCBFetcher()
            selic_df = bcb.get_selic(period_days=30)
            if not selic_df.empty:
                selic = selic_df["valor"].iloc[-1]
        except Exception as e:
            logger.warning(f"Falha ao buscar Selic: {e}")

        # IPCA via BCB (acumulado 12 meses)
        try:
            bcb = BCBFetcher()
            ipca_df = bcb.get_ipca(period_days=365)
            if not ipca_df.empty:
                # Acumula variações mensais
                monthly_rates = ipca_df["valor"] / 100
                ipca = ((1 + monthly_rates).prod() - 1) * 100
        except Exception as e:
            logger.warning(f"Falha ao buscar IPCA: {e}")

        # Câmbio (PTAX) via BCB
        try:
            bcb = BCBFetcher()
            ptax_df = bcb.get_ptax(period_days=7)
            if not ptax_df.empty:
                cambio = ptax_df["valor"].iloc[-1]
        except Exception as e:
            logger.warning(f"Falha ao buscar PTAX: {e}")

        # PIB via IBGE
        try:
            ibge = IBGEFetcher()
            pib_df = ibge.get_pib(quarters=4)
            if not pib_df.empty:
                pib_growth = pib_df["valor"].iloc[-1]
        except Exception as e:
            logger.warning(f"Falha ao buscar PIB: {e}")

        # Sumário textual
        summary = self._generate_summary(selic, ipca, cambio, pib_growth)

        return MacroContext(
            selic=selic,
            ipca=ipca,
            cambio=cambio,
            pib_growth=pib_growth,
            summary=summary,
        )

    def _generate_summary(
        self,
        selic: float | None,
        ipca: float | None,
        cambio: float | None,
        pib: float | None,
    ) -> str:
        """Gera sumário textual do cenário macro."""
        parts = []

        if selic is not None:
            parts.append(f"Selic a {selic:.2f}% a.a.")
        if ipca is not None:
            parts.append(f"IPCA acumulado {ipca:.2f}%")
        if cambio is not None:
            parts.append(f"Câmbio R$ {cambio:.2f}")
        if pib is not None:
            parts.append(f"PIB {pib:+.1f}%")

        return "; ".join(parts) if parts else "Dados macro indisponíveis"
