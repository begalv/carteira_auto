"""Analyzer macroeconômico — indicadores BCB e IBGE.

Node DAG: name="analyze_macro", deps=[]
Produz: ctx["macro_context"] -> MacroContext
"""

import traceback

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import MacroContext
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution
from carteira_auto.utils.helpers import accumulate_rates

logger = get_logger(__name__)


class MacroAnalyzer(Node):
    """Consolida contexto macroeconômico a partir de BCB e IBGE.

    Não depende de outros nodes — busca dados diretamente.
    Falhas parciais são registradas em ctx["_errors"] mas não impedem
    o retorno dos indicadores que foram obtidos com sucesso.

    Produz no contexto:
        - "macro_context": MacroContext
    """

    name = "analyze_macro"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        macro = self._build_macro_context(ctx)
        ctx["macro_context"] = macro
        logger.info(
            f"Macro: Selic={macro.selic}% a.a., IPCA 12m={macro.ipca:.2f}%, "
            f"CDI 12m={macro.cdi:.2f}%, USD={macro.cambio}, "
            f"PIB={macro.pib_growth}%, Desocup={macro.desocupacao}%"
            if all(v is not None for v in [macro.ipca, macro.cdi])
            else f"Macro: {macro.summary}"
        )
        return ctx

    def _build_macro_context(self, ctx: PipelineContext) -> MacroContext:
        """Busca indicadores BCB e IBGE e consolida contexto macro completo."""
        from carteira_auto.data.fetchers import BCBFetcher, IBGEFetcher

        ctx.setdefault("_errors", {})
        errors: list[str] = []

        selic = cdi = ipca = igpm = inpc = poupanca = tr = None
        cambio = dolar_ptax_venda = None
        pib_growth = desocupacao = None

        bcb = BCBFetcher()

        # ---- Selic: valor mais recente (% a.a.) ----
        try:
            selic_df = bcb.get_selic(period_days=30)
            if not selic_df.empty:
                selic = float(selic_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar Selic: {e}\n{traceback.format_exc()}")
            errors.append(f"Selic: {e}")

        # ---- CDI: acumulado 12 meses (% a.a.) via composição de % a.d. ----
        try:
            cdi_df = bcb.get_cdi(period_days=365)
            if not cdi_df.empty:
                cdi = accumulate_rates(cdi_df["valor"], "a.d.")
        except Exception as e:
            logger.error(f"Falha ao buscar CDI: {e}\n{traceback.format_exc()}")
            errors.append(f"CDI: {e}")

        # ---- IPCA: acumulado 12 meses (%) via composição de variações mensais ----
        try:
            ipca_df = bcb.get_ipca(period_days=365)
            if not ipca_df.empty:
                ipca = accumulate_rates(ipca_df["valor"], "a.m.")
        except Exception as e:
            logger.error(f"Falha ao buscar IPCA: {e}\n{traceback.format_exc()}")
            errors.append(f"IPCA: {e}")

        # ---- IGP-M: acumulado 12 meses (%) ----
        try:
            igpm_df = bcb.get_igpm(period_days=365)
            if not igpm_df.empty:
                igpm = accumulate_rates(igpm_df["valor"], "a.m.")
        except Exception as e:
            logger.error(f"Falha ao buscar IGP-M: {e}\n{traceback.format_exc()}")
            errors.append(f"IGP-M: {e}")

        # ---- INPC: acumulado 12 meses (%) ----
        try:
            inpc_df = bcb.get_inpc(period_days=365)
            if not inpc_df.empty:
                inpc = accumulate_rates(inpc_df["valor"], "a.m.")
        except Exception as e:
            logger.error(f"Falha ao buscar INPC: {e}\n{traceback.format_exc()}")
            errors.append(f"INPC: {e}")

        # ---- Poupança: acumulado 12 meses (% a.a.) via composição de % a.m. ----
        try:
            poupanca_df = bcb.get_poupanca(period_days=365)
            if not poupanca_df.empty:
                poupanca = accumulate_rates(poupanca_df["valor"].tail(12), "a.m.")
        except Exception as e:
            logger.error(f"Falha ao buscar Poupança: {e}\n{traceback.format_exc()}")
            errors.append(f"Poupança: {e}")

        # ---- TR: acumulada 12 meses (% a.a.) via composição de % a.m. ----
        try:
            tr_df = bcb.get_tr(period_days=365)
            if not tr_df.empty:
                tr = accumulate_rates(tr_df["valor"].tail(12), "a.m.")
        except Exception as e:
            logger.error(f"Falha ao buscar TR: {e}\n{traceback.format_exc()}")
            errors.append(f"TR: {e}")

        # ---- PTAX compra: valor mais recente (R$/USD) ----
        try:
            ptax_df = bcb.get_ptax(period_days=7)
            if not ptax_df.empty:
                cambio = float(ptax_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar PTAX compra: {e}\n{traceback.format_exc()}")
            errors.append(f"PTAX: {e}")

        # ---- PTAX venda: valor mais recente (R$/USD) ----
        try:
            ptax_venda_df = bcb.get_ptax_venda(period_days=7)
            if not ptax_venda_df.empty:
                dolar_ptax_venda = float(ptax_venda_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar PTAX venda: {e}\n{traceback.format_exc()}")
            errors.append(f"PTAX venda: {e}")

        # ---- PIB: variação % último trimestre disponível ----
        try:
            ibge = IBGEFetcher()
            pib_df = ibge.get_pib(quarters=4)
            if not pib_df.empty:
                pib_growth = float(pib_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar PIB: {e}\n{traceback.format_exc()}")
            errors.append(f"PIB: {e}")

        # ---- Desocupação PNAD: valor mais recente (%) ----
        try:
            ibge = IBGEFetcher()
            desoc_df = ibge.get_unemployment(quarters=4)
            if not desoc_df.empty:
                desocupacao = float(desoc_df["valor"].iloc[-1])
        except Exception as e:
            logger.error(f"Falha ao buscar desocupação: {e}\n{traceback.format_exc()}")
            errors.append(f"Desocupação: {e}")

        if errors:
            ctx["_errors"]["analyze_macro.partial"] = "; ".join(errors)

        summary = self._generate_summary(selic, ipca, cambio, pib_growth, desocupacao)

        return MacroContext(
            selic=selic,
            cdi=cdi,
            ipca=ipca,
            igpm=igpm,
            inpc=inpc,
            poupanca=poupanca,
            tr=tr,
            cambio=cambio,
            dolar_ptax_venda=dolar_ptax_venda,
            pib_growth=pib_growth,
            desocupacao=desocupacao,
            summary=summary,
        )

    def _generate_summary(
        self,
        selic: float | None,
        ipca: float | None,
        cambio: float | None,
        pib: float | None,
        desocupacao: float | None,
    ) -> str:
        """Gera sumário textual do cenário macro."""
        parts = []

        if selic is not None:
            parts.append(f"Selic {selic:.2f}% a.a.")
        if ipca is not None:
            parts.append(f"IPCA 12m {ipca:.2f}%")
        if cambio is not None:
            parts.append(f"USD R${cambio:.2f}")
        if pib is not None:
            parts.append(f"PIB {pib:+.1f}%")
        if desocupacao is not None:
            parts.append(f"Desocupação {desocupacao:.1f}%")

        return "; ".join(parts) if parts else "Dados macro indisponíveis"
