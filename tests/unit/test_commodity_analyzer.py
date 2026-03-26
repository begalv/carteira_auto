"""Testes do CommodityAnalyzer."""

from unittest.mock import patch

import pandas as pd
from carteira_auto.analyzers.commodity_analyzer import (
    CommodityAnalyzer,
)
from carteira_auto.core.engine import PipelineContext
from carteira_auto.core.models import CommodityMetrics


def _make_commodity_data(
    n_days: int = 1260,
    base_prices: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Cria DataFrame multi-ticker simulando yf.download(group_by='ticker').

    Args:
        n_days: Número de dias de dados (default: 5 anos = 1260 dias úteis).
        base_prices: Dict {ticker: preço_base}. Se None, usa defaults.
    """
    if base_prices is None:
        base_prices = {
            "CL=F": 70.0,
            "BZ=F": 75.0,
            "GC=F": 1800.0,
            "SI=F": 25.0,
            "ZS=F": 1400.0,
            "ZC=F": 600.0,
            "ZW=F": 700.0,
        }

    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n_days)
    arrays = []
    ticker_names = []
    col_names = []

    for ticker, base in base_prices.items():
        # Preço crescente suave
        close_vals = [base + i * (base * 0.0002) for i in range(n_days)]
        for col_name, vals in [
            ("Open", [v * 0.99 for v in close_vals]),
            ("High", [v * 1.01 for v in close_vals]),
            ("Low", [v * 0.98 for v in close_vals]),
            ("Close", close_vals),
            ("Volume", [1000000] * n_days),
        ]:
            arrays.append(vals)
            ticker_names.append(ticker)
            col_names.append(col_name)

    columns = pd.MultiIndex.from_arrays([ticker_names, col_names])
    return pd.DataFrame(
        dict(zip(range(len(arrays)), arrays, strict=False)),
        index=dates,
    ).set_axis(columns, axis=1)


def _make_commodity_data_expansion(n_days: int = 1260) -> pd.DataFrame:
    """Dados onde preço atual >> média 5y (> 120%) → expansion."""
    base_prices = {
        "BZ=F": 50.0,  # Base baixa, mas crescente → atual será >>120% da média
        "GC=F": 1200.0,
        "ZS=F": 900.0,
    }
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n_days)
    arrays = []
    ticker_names = []
    col_names = []

    for ticker, base in base_prices.items():
        # Crescimento forte: preço final será ~2x base
        close_vals = [base * (0.5 + 1.5 * i / n_days) for i in range(n_days)]
        arrays.append(close_vals)
        ticker_names.append(ticker)
        col_names.append("Close")

    columns = pd.MultiIndex.from_arrays([ticker_names, col_names])
    return pd.DataFrame(
        dict(zip(range(len(arrays)), arrays, strict=False)),
        index=dates,
    ).set_axis(columns, axis=1)


def _make_commodity_data_contraction(n_days: int = 1260) -> pd.DataFrame:
    """Dados onde preço atual entre 80-100% da média 5y → contraction."""
    base_prices = {
        "BZ=F": 100.0,
        "GC=F": 2000.0,
        "ZS=F": 1500.0,
    }
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n_days)
    arrays = []
    ticker_names = []
    col_names = []

    for ticker, base in base_prices.items():
        # Declinante: preço final será ~85% da média
        close_vals = [base * (1.15 - 0.3 * i / n_days) for i in range(n_days)]
        arrays.append(close_vals)
        ticker_names.append(ticker)
        col_names.append("Close")

    columns = pd.MultiIndex.from_arrays([ticker_names, col_names])
    return pd.DataFrame(
        dict(zip(range(len(arrays)), arrays, strict=False)),
        index=dates,
    ).set_axis(columns, axis=1)


def _make_commodity_data_trough(n_days: int = 1260) -> pd.DataFrame:
    """Dados onde preço atual < 80% da média 5y → trough."""
    base_prices = {
        "BZ=F": 100.0,
        "GC=F": 2000.0,
        "ZS=F": 1500.0,
    }
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n_days)
    arrays = []
    ticker_names = []
    col_names = []

    for ticker, base in base_prices.items():
        # Queda forte: preço final será ~50% da média
        close_vals = [base * (1.5 - 1.0 * i / n_days) for i in range(n_days)]
        arrays.append(close_vals)
        ticker_names.append(ticker)
        col_names.append("Close")

    columns = pd.MultiIndex.from_arrays([ticker_names, col_names])
    return pd.DataFrame(
        dict(zip(range(len(arrays)), arrays, strict=False)),
        index=dates,
    ).set_axis(columns, axis=1)


class TestCommodityAnalyzer:
    """Testes do CommodityAnalyzer."""

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_commodity_metrics_completas(self, mock_yahoo_cls):
        """Yahoo retorna dados para todos os tickers."""
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = _make_commodity_data()

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        assert isinstance(metrics, CommodityMetrics)
        assert metrics.oil_wti is not None
        assert metrics.oil_brent is not None
        assert metrics.gold is not None
        assert metrics.silver is not None
        assert metrics.soybean is not None
        assert metrics.corn is not None
        assert metrics.wheat is not None
        assert metrics.summary is not None

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_variacao_precos(self, mock_yahoo_cls):
        """Preços conhecidos → variações positivas (série crescente)."""
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = _make_commodity_data()

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        # Série crescente → variações devem ser positivas
        assert metrics.oil_change_1m is not None and metrics.oil_change_1m > 0
        assert metrics.gold_change_1m is not None and metrics.gold_change_1m > 0
        assert metrics.gold_change_3m is not None and metrics.gold_change_3m > 0
        assert metrics.soybean_change_1m is not None and metrics.soybean_change_1m > 0

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_cycle_signal_expansion(self, mock_yahoo_cls):
        """Preço atual > 120% da média 5y → expansion."""
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = _make_commodity_data_expansion()

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        assert metrics.cycle_signal == "expansion"

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_cycle_signal_contraction(self, mock_yahoo_cls):
        """Preço atual entre 80-100% da média 5y → contraction."""
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = (
            _make_commodity_data_contraction()
        )

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        assert metrics.cycle_signal == "contraction"

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_cycle_signal_trough(self, mock_yahoo_cls):
        """Preço atual < 80% da média 5y → trough."""
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = _make_commodity_data_trough()

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        assert metrics.cycle_signal == "trough"

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_falha_parcial(self, mock_yahoo_cls):
        """DataFrame parcial — só 2 tickers retornam dados."""
        # Só BZ=F e GC=F com dados
        partial_data = _make_commodity_data(base_prices={"BZ=F": 80.0, "GC=F": 2000.0})
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = partial_data

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        assert metrics.oil_brent is not None
        assert metrics.gold is not None
        assert metrics.oil_wti is None
        assert metrics.soybean is None

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_commodity_index(self, mock_yahoo_cls):
        """Média ponderada das variações 3m."""
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.return_value = _make_commodity_data()

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        assert metrics.commodity_index_change_3m is not None
        # Série crescente → índice deve ser positivo
        assert metrics.commodity_index_change_3m > 0

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.YahooFinanceFetcher")
    def test_falha_total_yahoo(self, mock_yahoo_cls):
        """Yahoo falha completamente → métricas vazias."""
        yahoo = mock_yahoo_cls.return_value
        yahoo.get_historical_price_data.side_effect = ConnectionError("Yahoo down")

        analyzer = CommodityAnalyzer()
        ctx = PipelineContext()
        result = analyzer.run(ctx)

        metrics = result["commodity_metrics"]
        assert metrics.oil_brent is None
        assert metrics.gold is None
        assert metrics.cycle_signal is None
        assert metrics.summary == "Dados de commodities indisponíveis"
        assert "analyze_commodities.partial" in ctx["_errors"]
