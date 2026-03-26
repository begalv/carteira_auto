"""Testes do CurrencyAnalyzer."""

from unittest.mock import patch

import pandas as pd
import pytest
from carteira_auto.analyzers.currency_analyzer import CurrencyAnalyzer
from carteira_auto.core.engine import PipelineContext
from carteira_auto.core.models import CurrencyMetrics


def _make_ptax_series(n_days: int = 300, base: float = 5.0) -> pd.DataFrame:
    """Cria série PTAX sintética com tendência suave."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n_days)
    values = [base + i * 0.001 for i in range(n_days)]
    return pd.DataFrame({"data": dates, "valor": values})


def _make_selic_series(value: float = 14.75) -> pd.DataFrame:
    """Cria série Selic com valor constante."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=5)
    return pd.DataFrame({"data": dates, "valor": [value] * 5})


def _make_fred_series(value: float = 3.50) -> pd.DataFrame:
    """Cria série FRED DFF."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=10)
    return pd.DataFrame(
        {
            "date": dates,
            "value": [value] * 10,
            "series_id": ["DFF"] * 10,
        }
    )


def _make_dxy_series(value: float = 104.5, n_days: int = 60) -> pd.DataFrame:
    """Cria série DXY do Yahoo Finance."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n_days)
    close_vals = [value - (n_days - i) * 0.1 for i in range(n_days)]
    return pd.DataFrame({"Close": close_vals}, index=dates)


def _make_cambio_real_series(value: float = 123.71) -> pd.DataFrame:
    """Cria série de câmbio real efetivo."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=3)
    return pd.DataFrame({"data": dates, "valor": [value] * 3})


class TestCurrencyAnalyzer:
    """Testes do CurrencyAnalyzer."""

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    @patch("carteira_auto.data.fetchers.FREDFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_currency_metrics_completas(
        self, mock_bcb_cls, mock_fred_cls, mock_yahoo_cls
    ):
        """Todos os fetchers retornam dados — verifica todos os campos."""
        bcb = mock_bcb_cls.return_value
        bcb.get_ptax.return_value = _make_ptax_series(300, 5.0)
        bcb.get_ptax_venda.return_value = pd.DataFrame(
            {
                "data": pd.bdate_range(end=pd.Timestamp.now(), periods=3),
                "valor": [5.05, 5.06, 5.07],
            }
        )
        bcb.get_selic.return_value = _make_selic_series(14.75)
        bcb.get_indicator.return_value = _make_cambio_real_series(123.71)

        fred = mock_fred_cls.return_value
        fred.get_series.return_value = _make_fred_series(3.50)

        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = _make_dxy_series(104.5)

        analyzer = CurrencyAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["currency_metrics"]
        assert isinstance(metrics, CurrencyMetrics)
        assert metrics.usd_brl is not None
        assert metrics.usd_brl_ptax_venda == pytest.approx(5.07)
        assert metrics.usd_brl_change_1m is not None
        assert metrics.dxy is not None
        assert metrics.selic_rate == pytest.approx(14.75)
        assert metrics.fed_funds_rate == pytest.approx(3.50)
        assert metrics.carry_spread is not None
        assert metrics.taxa_cambio_real_efetiva == pytest.approx(123.71)
        assert metrics.summary is not None
        assert "_errors" not in ctx or "analyze_currency" not in str(
            ctx.get("_errors", {})
        )

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    @patch("carteira_auto.data.fetchers.FREDFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_carry_spread_calculo(self, mock_bcb_cls, mock_fred_cls, mock_yahoo_cls):
        """Selic=14.75, Fed=3.50 → carry=11.25."""
        bcb = mock_bcb_cls.return_value
        bcb.get_ptax.return_value = pd.DataFrame(columns=["data", "valor"])
        bcb.get_ptax_venda.return_value = pd.DataFrame(columns=["data", "valor"])
        bcb.get_selic.return_value = _make_selic_series(14.75)
        bcb.get_indicator.return_value = pd.DataFrame(columns=["data", "valor"])

        fred = mock_fred_cls.return_value
        fred.get_series.return_value = _make_fred_series(3.50)

        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = pd.DataFrame()

        analyzer = CurrencyAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["currency_metrics"]
        assert metrics.carry_spread == pytest.approx(11.25)
        assert metrics.selic_rate == pytest.approx(14.75)
        assert metrics.fed_funds_rate == pytest.approx(3.50)

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    @patch("carteira_auto.data.fetchers.FREDFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_variacao_cambio(self, mock_bcb_cls, mock_fred_cls, mock_yahoo_cls):
        """Série PTAX sintética → verifica change_1m/3m/12m."""
        # Série com 300 dias úteis, valor crescente de 5.0 a ~5.3
        ptax = _make_ptax_series(300, 5.0)

        bcb = mock_bcb_cls.return_value
        bcb.get_ptax.return_value = ptax
        bcb.get_ptax_venda.return_value = pd.DataFrame(columns=["data", "valor"])
        bcb.get_selic.return_value = pd.DataFrame(columns=["data", "valor"])
        bcb.get_indicator.return_value = pd.DataFrame(columns=["data", "valor"])

        fred = mock_fred_cls.return_value
        fred.get_series.return_value = pd.DataFrame(
            columns=["date", "value", "series_id"]
        )

        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = pd.DataFrame()

        analyzer = CurrencyAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["currency_metrics"]
        # Valor corrente: 5.0 + 299*0.001 = 5.299
        assert metrics.usd_brl == pytest.approx(5.299)
        # Variações devem ser positivas (série crescente)
        assert metrics.usd_brl_change_1m is not None
        assert metrics.usd_brl_change_1m > 0
        assert metrics.usd_brl_change_3m is not None
        assert metrics.usd_brl_change_3m > 0
        assert metrics.usd_brl_change_12m is not None
        assert metrics.usd_brl_change_12m > 0

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    @patch("carteira_auto.data.fetchers.FREDFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_falha_parcial_fred(self, mock_bcb_cls, mock_fred_cls, mock_yahoo_cls):
        """FRED falha → carry_spread=None, USD/BRL preenchido."""
        bcb = mock_bcb_cls.return_value
        bcb.get_ptax.return_value = _make_ptax_series(300, 5.0)
        bcb.get_ptax_venda.return_value = pd.DataFrame(columns=["data", "valor"])
        bcb.get_selic.return_value = _make_selic_series(14.75)
        bcb.get_indicator.return_value = pd.DataFrame(columns=["data", "valor"])

        fred = mock_fred_cls.return_value
        fred.get_series.side_effect = PermissionError("FRED_API_KEY não configurada")

        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = pd.DataFrame()

        analyzer = CurrencyAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["currency_metrics"]
        assert metrics.usd_brl is not None  # BCB funcionou
        assert metrics.selic_rate == pytest.approx(14.75)
        assert metrics.fed_funds_rate is None  # FRED falhou
        assert metrics.carry_spread is None  # Sem Fed, sem carry
        assert "analyze_currency.partial" in ctx.get("_errors", {})
        assert "Fed Funds" in ctx["_errors"]["analyze_currency.partial"]

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    @patch("carteira_auto.data.fetchers.FREDFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_falha_parcial_yahoo(self, mock_bcb_cls, mock_fred_cls, mock_yahoo_cls):
        """Yahoo falha → DXY=None, PTAX preenchido."""
        bcb = mock_bcb_cls.return_value
        bcb.get_ptax.return_value = _make_ptax_series(300, 5.0)
        bcb.get_ptax_venda.return_value = pd.DataFrame(columns=["data", "valor"])
        bcb.get_selic.return_value = pd.DataFrame(columns=["data", "valor"])
        bcb.get_indicator.return_value = pd.DataFrame(columns=["data", "valor"])

        fred = mock_fred_cls.return_value
        fred.get_series.return_value = pd.DataFrame(
            columns=["date", "value", "series_id"]
        )

        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.side_effect = ConnectionError("Yahoo timeout")

        analyzer = CurrencyAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["currency_metrics"]
        assert metrics.usd_brl is not None  # BCB funcionou
        assert metrics.dxy is None  # Yahoo falhou
        assert "analyze_currency.partial" in ctx.get("_errors", {})
        assert "DXY" in ctx["_errors"]["analyze_currency.partial"]

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    @patch("carteira_auto.data.fetchers.FREDFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_falha_total(self, mock_bcb_cls, mock_fred_cls, mock_yahoo_cls):
        """Tudo falha → CurrencyMetrics vazio, erros registrados."""
        bcb = mock_bcb_cls.return_value
        bcb.get_ptax.side_effect = ConnectionError("BCB offline")
        bcb.get_ptax_venda.side_effect = ConnectionError("BCB offline")
        bcb.get_selic.side_effect = ConnectionError("BCB offline")
        bcb.get_indicator.side_effect = ConnectionError("BCB offline")

        fred = mock_fred_cls.return_value
        fred.get_series.side_effect = PermissionError("No key")

        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.side_effect = ConnectionError("Yahoo down")

        analyzer = CurrencyAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["currency_metrics"]
        assert metrics.usd_brl is None
        assert metrics.dxy is None
        assert metrics.carry_spread is None
        assert metrics.summary == "Dados cambiais indisponíveis"
        assert "analyze_currency.partial" in ctx["_errors"]


class TestPctChange:
    """Testes do método estático _pct_change."""

    def test_variacao_positiva(self):
        series = pd.Series([100.0, 105.0, 110.0])
        result = CurrencyAnalyzer._pct_change(series, 1)
        assert result == pytest.approx(4.76, abs=0.01)

    def test_serie_insuficiente(self):
        series = pd.Series([100.0, 105.0])
        result = CurrencyAnalyzer._pct_change(series, 5)
        assert result is None

    def test_valor_passado_zero(self):
        series = pd.Series([0.0, 105.0])
        result = CurrencyAnalyzer._pct_change(series, 1)
        assert result is None
