"""Testes unitários para o YahooFinanceFetcher.

Todos os testes usam mocks — nenhuma chamada real à API do Yahoo Finance.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# Precisamos mockar settings e yfinance ANTES de importar o fetcher,
# pois o módulo acessa settings no nível de módulo (decorators) e no __init__.
@pytest.fixture(autouse=True)
def _mock_settings(monkeypatch):
    """Mocka as configurações globais usadas pelo módulo yahoo_fetcher."""
    mock_yahoo_config = MagicMock()
    mock_yahoo_config.TIMEOUT = 30
    mock_yahoo_config.RETRIES = 3
    mock_yahoo_config.RATE_LIMIT = 30

    mock_settings = MagicMock()
    mock_settings.yahoo = mock_yahoo_config
    mock_settings.DEBUG = False

    monkeypatch.setattr(
        "carteira_auto.data.fetchers.yahoo_fetcher.settings", mock_settings
    )


@pytest.fixture
def fetcher():
    """Cria uma instância do YahooFinanceFetcher com yfinance mockado."""
    with patch("carteira_auto.data.fetchers.yahoo_fetcher.yf"):
        from carteira_auto.data.fetchers.yahoo_fetcher import YahooFinanceFetcher

        return YahooFinanceFetcher(max_workers=2)


# ============================================================================
# TESTES DE normalize_br_ticker
# ============================================================================


class TestNormalizeBrTicker:
    """Testes para o método estático normalize_br_ticker."""

    def test_acao_b3_recebe_sufixo_sa(self, fetcher):
        """Ticker de ação B3 (ex: PETR4) deve receber .SA."""
        assert fetcher.normalize_br_ticker("PETR4") == "PETR4.SA"

    def test_acao_b3_vale3(self, fetcher):
        """Ticker VALE3 deve receber .SA."""
        assert fetcher.normalize_br_ticker("VALE3") == "VALE3.SA"

    def test_ticker_ja_com_sufixo_nao_duplica(self, fetcher):
        """Ticker que já tem .SA não deve receber outro sufixo."""
        assert fetcher.normalize_br_ticker("PETR4.SA") == "PETR4.SA"

    def test_indice_com_caractere_especial_recebe_sa(self, fetcher):
        """Tickers de índice (^BVSP) recebem .SA para Yahoo Finance."""
        assert fetcher.normalize_br_ticker("^BVSP") == "^BVSP.SA"

    def test_ticker_americano_nao_modifica(self, fetcher):
        """Tickers que não seguem padrão B3 (ex: AAPL) não devem ser alterados."""
        assert fetcher.normalize_br_ticker("AAPL") == "AAPL"

    def test_fii_recebe_sufixo_sa(self, fetcher):
        """Fundo imobiliário (ex: HGLG11) deve receber .SA."""
        assert fetcher.normalize_br_ticker("HGLG11") == "HGLG11.SA"

    def test_tesouro_direto_nao_modifica(self, fetcher):
        """Tickers de Tesouro Direto (NON_YAHOO_TICKERS) não devem ser alterados."""
        assert fetcher.normalize_br_ticker("NTNB") == "NTNB"
        assert fetcher.normalize_br_ticker("LFT") == "LFT"

    def test_ticker_com_hifen_nao_modifica(self, fetcher):
        """Tickers com hífen não devem ser alterados."""
        assert fetcher.normalize_br_ticker("BRK-B") == "BRK-B"


# ============================================================================
# TESTES DE get_multiple_prices
# ============================================================================


class TestGetMultiplePrices:
    """Testes para o método get_multiple_prices."""

    def test_lista_vazia_retorna_dict_vazio(self, fetcher):
        """Lista vazia de tickers deve retornar dicionário vazio."""
        resultado = fetcher.get_multiple_prices([])
        assert resultado == {}

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_ticker_unico_retorna_preco(self, mock_download, fetcher):
        """Um único ticker deve retornar seu preço corretamente."""
        # Simula DataFrame com coluna Close para um único ticker
        df = pd.DataFrame({"Close": [25.50, 26.00, 26.30]})
        mock_download.return_value = df

        resultado = fetcher.get_multiple_prices(["PETR4"])

        assert "PETR4" in resultado
        assert resultado["PETR4"] == pytest.approx(26.30)
        mock_download.assert_called_once()

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_multiplos_tickers_retorna_precos(self, mock_download, fetcher):
        """Múltiplos tickers devem retornar preços para cada um."""
        # Simula DataFrame multi-ticker com MultiIndex nas colunas
        arrays = [
            ["Close", "Close", "Open", "Open"],
            ["PETR4.SA", "VALE3.SA", "PETR4.SA", "VALE3.SA"],
        ]
        tuples = list(zip(*arrays, strict=False))
        index = pd.MultiIndex.from_tuples(tuples)
        data = pd.DataFrame(
            [[25.0, 60.0, 24.0, 59.0], [26.0, 61.0, 25.0, 60.0]],
            columns=index,
        )
        mock_download.return_value = data

        resultado = fetcher.get_multiple_prices(["PETR4", "VALE3"])

        assert resultado["PETR4"] == pytest.approx(26.0)
        assert resultado["VALE3"] == pytest.approx(61.0)

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_download_vazio_retorna_none_para_todos(self, mock_download, fetcher):
        """Se o download retorna DataFrame vazio, todos os preços devem ser None."""
        mock_download.return_value = pd.DataFrame()

        resultado = fetcher.get_multiple_prices(["PETR4", "VALE3"])

        assert resultado["PETR4"] is None
        assert resultado["VALE3"] is None

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_excecao_no_download_retorna_none(self, mock_download, fetcher):
        """Se o download lanca excecao, todos os precos devem ser None."""
        mock_download.side_effect = Exception("Erro de conexao")

        resultado = fetcher.get_multiple_prices(["PETR4"])

        assert resultado["PETR4"] is None

    def test_tickers_tesouro_retorna_none(self, fetcher):
        """Tickers de Tesouro Direto (NON_YAHOO_TICKERS) devem retornar None."""
        resultado = fetcher.get_multiple_prices(["NTNB", "LFT"])

        assert resultado["NTNB"] is None
        assert resultado["LFT"] is None

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_mix_yahoo_e_tesouro(self, mock_download, fetcher):
        """Mistura de tickers Yahoo e Tesouro: Yahoo busca, Tesouro retorna None."""
        df = pd.DataFrame({"Close": [25.50, 26.00]})
        mock_download.return_value = df

        resultado = fetcher.get_multiple_prices(["PETR4", "NTNB"])

        assert resultado["PETR4"] == pytest.approx(26.0)
        assert resultado["NTNB"] is None


# ============================================================================
# TESTES DE get_historical_price_data
# ============================================================================


class TestGetHistoricalPriceData:
    """Testes para o método get_historical_price_data."""

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_retorna_dataframe_com_dados(self, mock_download, fetcher):
        """Deve retornar DataFrame com dados historicos quando download funciona."""
        index = pd.date_range("2024-01-01", periods=5, freq="D")
        df = pd.DataFrame(
            {
                "Open": [25.0, 25.5, 26.0, 25.8, 26.2],
                "Close": [25.5, 26.0, 25.8, 26.2, 26.5],
                "High": [26.0, 26.5, 26.2, 26.5, 27.0],
                "Low": [24.5, 25.0, 25.5, 25.5, 26.0],
                "Volume": [1000, 1100, 900, 1200, 1050],
            },
            index=index,
        )
        mock_download.return_value = df

        resultado = fetcher.get_historical_price_data("PETR4.SA")

        assert not resultado.empty
        assert len(resultado) == 5
        assert "Close" in resultado.columns

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_download_vazio_retorna_dataframe_vazio(self, mock_download, fetcher):
        """Se o download retorna vazio, deve retornar DataFrame vazio."""
        mock_download.return_value = pd.DataFrame()

        resultado = fetcher.get_historical_price_data("PETR4.SA")

        assert isinstance(resultado, pd.DataFrame)
        assert resultado.empty

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_excecao_retorna_dataframe_vazio(self, mock_download, fetcher):
        """Se o download lanca excecao, deve retornar DataFrame vazio."""
        mock_download.side_effect = Exception("Timeout")

        resultado = fetcher.get_historical_price_data("PETR4.SA")

        assert isinstance(resultado, pd.DataFrame)
        assert resultado.empty

    @patch("carteira_auto.data.fetchers.yahoo_fetcher.download")
    def test_parametros_passados_corretamente(self, mock_download, fetcher):
        """Verifica que period e interval sao passados ao download."""
        mock_download.return_value = pd.DataFrame()

        fetcher.get_historical_price_data("PETR4.SA", period="1y", interval="1wk")

        mock_download.assert_called_once()
        call_kwargs = mock_download.call_args
        assert (
            call_kwargs.kwargs.get("period") == "1y"
            or call_kwargs[1].get("period") == "1y"
        )
