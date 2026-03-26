"""Testes do FiscalAnalyzer."""

from unittest.mock import patch

import pandas as pd
import pytest
from carteira_auto.analyzers.fiscal_analyzer import FiscalAnalyzer
from carteira_auto.core.engine import PipelineContext
from carteira_auto.core.models import FiscalMetrics


def _make_fiscal_series(
    value: float, n_months: int = 24, trend: float = 0.0
) -> pd.DataFrame:
    """Cria série fiscal mensal sintética.

    Args:
        value: Valor base da série.
        n_months: Número de meses de dados.
        trend: Variação mensal (positivo = crescente).
    """
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_months, freq="MS")
    values = [value + i * trend for i in range(n_months)]
    return pd.DataFrame({"data": dates, "valor": values})


def _setup_bcb_mock(mock_bcb_cls, fiscal_values: dict[str, float | None]):
    """Configura mock do BCBFetcher para retornar valores fiscais.

    Args:
        mock_bcb_cls: Mock da classe BCBFetcher.
        fiscal_values: Dict {nome_série: valor_float}.
    """
    bcb = mock_bcb_cls.return_value

    def mock_get_indicator(code, start_date=None, end_date=None):
        # Mapear código → nome
        code_to_name = {
            13762: "divida_bruta_pib",
            4503: "divida_liquida_pib",
            5793: "resultado_primario_pib",
            4649: "resultado_nominal",
            5727: "juros_nominais_pib",
        }
        name = code_to_name.get(code)
        if name is None or fiscal_values.get(name) is None:
            return pd.DataFrame(columns=["data", "valor"])

        value = fiscal_values[name]
        trend = fiscal_values.get(f"{name}_trend", 0.0)
        return _make_fiscal_series(value, n_months=24, trend=trend)

    bcb.get_indicator.side_effect = mock_get_indicator
    return bcb


class TestFiscalAnalyzer:
    """Testes do FiscalAnalyzer."""

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_fiscal_metrics_completas(self, mock_bcb_cls):
        """BCB retorna todas as 5 séries fiscais."""
        _setup_bcb_mock(
            mock_bcb_cls,
            {
                "divida_bruta_pib": 78.73,
                "divida_liquida_pib": 56.38,
                "resultado_primario_pib": 0.43,
                "resultado_nominal": -103689.0,
                "juros_nominais_pib": 8.48,
            },
        )

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert isinstance(metrics, FiscalMetrics)
        assert metrics.divida_bruta_pib == pytest.approx(78.73)
        assert metrics.divida_liquida_pib == pytest.approx(56.38)
        assert metrics.resultado_primario_pib == pytest.approx(0.43)
        assert metrics.resultado_nominal == pytest.approx(-103689.0)
        assert metrics.juros_nominais_pib == pytest.approx(8.48)
        assert metrics.fiscal_trajectory is not None
        assert metrics.summary is not None

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_trajetoria_improving(self, mock_bcb_cls):
        """Dívida caiu >1pp + primário melhorou → improving."""
        _setup_bcb_mock(
            mock_bcb_cls,
            {
                "divida_bruta_pib": 70.0,  # Abaixo de 75% → "stable" base
                "divida_liquida_pib": 50.0,
                "resultado_primario_pib": 1.0,
                "resultado_nominal": -50000.0,
                "juros_nominais_pib": 6.0,
                # Tendências: dívida caindo, primário subindo
                "divida_bruta_pib_trend": -0.2,  # -0.2/mês → -2.4pp em 12m
                "resultado_primario_pib_trend": 0.05,  # +0.05/mês → +0.6pp em 12m
            },
        )

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert metrics.fiscal_trajectory == "improving"

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_trajetoria_warning(self, mock_bcb_cls):
        """Dívida entre 75-80% → warning."""
        _setup_bcb_mock(
            mock_bcb_cls,
            {
                "divida_bruta_pib": 77.0,
                "divida_liquida_pib": 55.0,
                "resultado_primario_pib": 0.0,
                "resultado_nominal": -80000.0,
                "juros_nominais_pib": 7.0,
            },
        )

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert metrics.fiscal_trajectory == "warning"

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_trajetoria_critical(self, mock_bcb_cls):
        """Dívida entre 80-85% → critical."""
        _setup_bcb_mock(
            mock_bcb_cls,
            {
                "divida_bruta_pib": 82.0,
                "divida_liquida_pib": 60.0,
                "resultado_primario_pib": -0.5,
                "resultado_nominal": -120000.0,
                "juros_nominais_pib": 9.0,
            },
        )

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert metrics.fiscal_trajectory == "critical"

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_trajetoria_severe(self, mock_bcb_cls):
        """Dívida > 85% → severe."""
        _setup_bcb_mock(
            mock_bcb_cls,
            {
                "divida_bruta_pib": 90.0,
                "divida_liquida_pib": 70.0,
                "resultado_primario_pib": -2.0,
                "resultado_nominal": -200000.0,
                "juros_nominais_pib": 12.0,
            },
        )

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert metrics.fiscal_trajectory == "severe"

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_trajetoria_deteriorating(self, mock_bcb_cls):
        """Dívida <75% mas subindo >2pp + primário piorando → deteriorating."""
        _setup_bcb_mock(
            mock_bcb_cls,
            {
                "divida_bruta_pib": 70.0,  # Base estável
                "divida_liquida_pib": 50.0,
                "resultado_primario_pib": 0.0,
                "resultado_nominal": -80000.0,
                "juros_nominais_pib": 7.0,
                # Tendências: dívida subindo, primário caindo
                "divida_bruta_pib_trend": 0.3,  # +0.3/mês → +3.6pp em 12m
                "resultado_primario_pib_trend": -0.05,  # -0.05/mês → -0.6pp em 12m
            },
        )

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert metrics.fiscal_trajectory == "deteriorating"

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_falha_parcial(self, mock_bcb_cls):
        """Algumas séries falham → campos None para essas."""
        bcb = mock_bcb_cls.return_value

        call_count = [0]

        def mock_get_indicator(code, start_date=None, end_date=None):
            call_count[0] += 1
            if code == 13762:  # divida_bruta_pib funciona
                return _make_fiscal_series(78.0)
            elif code == 4503:  # divida_liquida_pib funciona
                return _make_fiscal_series(56.0)
            else:  # Resto falha
                raise ConnectionError("BCB timeout")

        bcb.get_indicator.side_effect = mock_get_indicator

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert metrics.divida_bruta_pib == pytest.approx(78.0)
        assert metrics.divida_liquida_pib == pytest.approx(56.0)
        assert metrics.resultado_primario_pib is None
        assert metrics.resultado_nominal is None
        assert metrics.juros_nominais_pib is None
        assert "analyze_fiscal.partial" in ctx["_errors"]

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_variacao_12m(self, mock_bcb_cls):
        """Série com 24 meses → verifica cálculo de variação 12m."""
        _setup_bcb_mock(
            mock_bcb_cls,
            {
                "divida_bruta_pib": 70.0,
                "divida_liquida_pib": 50.0,
                "resultado_primario_pib": 0.0,
                "resultado_nominal": -80000.0,
                "juros_nominais_pib": 7.0,
                # Tendência constante de +0.1pp/mês → variação 12m = +1.2pp
                "divida_bruta_pib_trend": 0.1,
                "resultado_primario_pib_trend": -0.05,
            },
        )

        analyzer = FiscalAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["fiscal_metrics"]
        assert metrics.divida_bruta_pib_change_12m is not None
        # Tendência 0.1/mês × 12 meses ≈ 1.2pp (comparando iloc[-1] vs iloc[-13])
        assert metrics.divida_bruta_pib_change_12m == pytest.approx(1.2, abs=0.1)
        assert metrics.resultado_primario_pib_change_12m is not None


class TestClassifyTrajectory:
    """Testes do método _classify_trajectory."""

    def test_none_divida_retorna_none(self):
        result = FiscalAnalyzer._classify_trajectory(None, None, None)
        assert result is None

    def test_stable_below_75(self):
        result = FiscalAnalyzer._classify_trajectory(70.0, 0.0, 0.0)
        assert result == "stable"

    def test_warning_between_75_80(self):
        result = FiscalAnalyzer._classify_trajectory(76.0, 0.0, 0.0)
        assert result == "warning"

    def test_critical_between_80_85(self):
        result = FiscalAnalyzer._classify_trajectory(83.0, 0.0, 0.0)
        assert result == "critical"

    def test_severe_above_85(self):
        result = FiscalAnalyzer._classify_trajectory(90.0, 0.0, 0.0)
        assert result == "severe"

    def test_improving_overrides(self):
        result = FiscalAnalyzer._classify_trajectory(82.0, -2.0, 1.0)
        assert result == "improving"

    def test_deteriorating_overrides_stable(self):
        result = FiscalAnalyzer._classify_trajectory(70.0, 3.0, -1.0)
        assert result == "deteriorating"

    def test_deteriorating_does_not_override_critical(self):
        result = FiscalAnalyzer._classify_trajectory(82.0, 3.0, -1.0)
        assert result == "critical"
