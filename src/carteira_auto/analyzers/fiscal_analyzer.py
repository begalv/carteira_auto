"""Analyzer fiscal do governo brasileiro.

Node DAG: name="analyze_fiscal", deps=[]
Produz: ctx["fiscal_metrics"] -> FiscalMetrics
"""

import traceback
from datetime import date, timedelta

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import FiscalMetrics
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)

# Séries SGS do BCB para indicadores fiscais
FISCAL_SERIES: dict[str, int] = {
    "divida_bruta_pib": 13762,
    "divida_liquida_pib": 4503,
    "resultado_primario_pib": 5793,
    "resultado_nominal": 4649,
    "juros_nominais_pib": 5727,
}


class FiscalAnalyzer(Node):
    """Analisa indicadores fiscais do governo brasileiro.

    Não depende de outros nodes — busca dados diretamente do BCBFetcher.
    Falhas parciais são registradas em ctx["_errors"] mas não impedem
    o retorno dos indicadores obtidos com sucesso.

    Produz no contexto:
        - "fiscal_metrics": FiscalMetrics
    """

    name = "analyze_fiscal"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        metrics = self._build_fiscal_metrics(ctx)
        ctx["fiscal_metrics"] = metrics
        logger.info(
            f"Fiscal: dívida bruta={metrics.divida_bruta_pib}% PIB, "
            f"primário={metrics.resultado_primario_pib}% PIB, "
            f"trajetória={metrics.fiscal_trajectory}"
            if metrics.divida_bruta_pib is not None
            else f"Fiscal: {metrics.summary}"
        )
        return ctx

    def _build_fiscal_metrics(self, ctx: PipelineContext) -> FiscalMetrics:
        """Busca indicadores fiscais do BCB e calcula métricas."""
        from carteira_auto.data.fetchers import BCBFetcher

        ctx.setdefault("_errors", {})
        errors: list[str] = []

        bcb = BCBFetcher()
        start = date.today() - timedelta(days=2 * 365)

        values: dict[str, float | None] = {}
        dfs: dict[str, object] = {}  # cache dos DataFrames para reusar no cálculo 12m

        # ---- Buscar cada série fiscal ----
        for name, code in FISCAL_SERIES.items():
            try:
                df = bcb.get_indicator(code, start_date=start)
                dfs[name] = df
                if not df.empty:
                    values[name] = float(df["valor"].iloc[-1])
                else:
                    values[name] = None
            except Exception as e:
                logger.error(
                    f"Falha ao buscar {name} (SGS {code}): "
                    f"{e}\n{traceback.format_exc()}"
                )
                errors.append(f"{name}: {e}")
                values[name] = None

        # ---- Calcular variação 12m (reutiliza DataFrames já buscados) ----
        divida_change_12m = None
        primario_change_12m = None

        try:
            df_divida = dfs.get("divida_bruta_pib")
            if df_divida is not None and not df_divida.empty and len(df_divida) >= 13:
                divida_change_12m = round(
                    float(df_divida["valor"].iloc[-1])
                    - float(df_divida["valor"].iloc[-13]),
                    2,
                )
        except Exception as e:
            logger.warning(f"Falha ao calcular variação 12m dívida: {e}")

        try:
            df_primario = dfs.get("resultado_primario_pib")
            if (
                df_primario is not None
                and not df_primario.empty
                and len(df_primario) >= 13
            ):
                primario_change_12m = round(
                    float(df_primario["valor"].iloc[-1])
                    - float(df_primario["valor"].iloc[-13]),
                    2,
                )
        except Exception as e:
            logger.warning(f"Falha ao calcular variação 12m primário: {e}")

        # ---- Classificar trajetória fiscal ----
        fiscal_trajectory = self._classify_trajectory(
            values.get("divida_bruta_pib"),
            divida_change_12m,
            primario_change_12m,
        )

        if errors:
            ctx["_errors"]["analyze_fiscal.partial"] = "; ".join(errors)

        summary = self._generate_summary(values, fiscal_trajectory)

        return FiscalMetrics(
            divida_bruta_pib=values.get("divida_bruta_pib"),
            divida_liquida_pib=values.get("divida_liquida_pib"),
            resultado_primario_pib=values.get("resultado_primario_pib"),
            resultado_nominal=values.get("resultado_nominal"),
            juros_nominais_pib=values.get("juros_nominais_pib"),
            divida_bruta_pib_change_12m=divida_change_12m,
            resultado_primario_pib_change_12m=primario_change_12m,
            fiscal_trajectory=fiscal_trajectory,
            summary=summary,
        )

    @staticmethod
    def _classify_trajectory(
        divida_bruta_pib: float | None,
        divida_change: float | None,
        primario_change: float | None,
    ) -> str | None:
        """Classifica trajetória fiscal com gradação 75/80/85.

        1) Nível absoluto de dívida/PIB:
           - >85% → "severe"
           - >80% → "critical"
           - >75% → "warning"
           - ≤75% → "stable"

        2) Ajuste pela tendência 12m (sobrescreve o nível absoluto):
           - Dívida caindo >1pp E primário melhorando → "improving"
             (sobrescreve qualquer nível, incluindo severe/critical — a tendência
              de melhora consistente é sinalizada independentemente do nível atual)
           - Dívida subindo >2pp E primário piorando → "deteriorating"
             (sobrescreve apenas "stable" ou "warning"; nível critical/severe
              já é suficientemente grave e não é rebaixado pela tendência)
        """
        if divida_bruta_pib is None:
            return None

        # Classificação por nível absoluto
        if divida_bruta_pib > 85:
            trajectory = "severe"
        elif divida_bruta_pib > 80:
            trajectory = "critical"
        elif divida_bruta_pib > 75:
            trajectory = "warning"
        else:
            trajectory = "stable"

        # Ajuste pela tendência 12m
        if divida_change is not None and primario_change is not None:
            if divida_change < -1 and primario_change > 0:
                trajectory = "improving"
            elif divida_change > 2 and primario_change < 0:
                if trajectory in ("stable", "warning"):
                    trajectory = "deteriorating"

        return trajectory

    @staticmethod
    def _generate_summary(
        values: dict[str, float | None],
        trajectory: str | None,
    ) -> str:
        """Gera sumário textual da situação fiscal."""
        parts = []
        if values.get("divida_bruta_pib") is not None:
            parts.append(f"Dívida bruta {values['divida_bruta_pib']:.1f}% PIB")
        if values.get("resultado_primario_pib") is not None:
            parts.append(f"primário {values['resultado_primario_pib']:+.2f}% PIB")
        if values.get("juros_nominais_pib") is not None:
            parts.append(f"juros {values['juros_nominais_pib']:.1f}% PIB")
        if trajectory is not None:
            parts.append(f"trajetória={trajectory}")
        return "; ".join(parts) if parts else "Dados fiscais indisponíveis"
