"""Testes para os nodes de ingestão (IngestNodes).

Verifica que cada IngestNode coleta dados do fetcher adequado e
persiste no DataLake via PipelineContext.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from carteira_auto.core.engine import PipelineContext
from carteira_auto.core.nodes.ingest_nodes import (
    IngestFundamentalsNode,
    IngestMacroNode,
    IngestNewsNode,
    IngestPricesNode,
)


@pytest.fixture
def ctx_with_lake(tmp_path):
    """Cria PipelineContext com DataLake temporário."""
    from carteira_auto.data.lake import DataLake

    lake = DataLake(tmp_path)
    ctx = PipelineContext()
    ctx["data_lake"] = lake
    return ctx


@pytest.fixture
def mock_portfolio():
    """Cria Portfolio mock com ativos de teste."""
    portfolio = MagicMock()
    asset1 = MagicMock()
    asset1.ticker = "PETR4.SA"
    asset1.classe = "Ações"
    asset2 = MagicMock()
    asset2.ticker = "HGLG11.SA"
    asset2.classe = "Fundos de Investimentos"
    asset3 = MagicMock()
    asset3.ticker = "NTNB-2035"
    asset3.classe = "Renda Fixa"
    portfolio.assets = [asset1, asset2, asset3]
    return portfolio


# =============================================================================
# IngestPricesNode
# =============================================================================


class TestIngestPricesNode:
    """Testes para IngestPricesNode."""

    def test_collect_tickers_sem_portfolio(self):
        """Coleta apenas tickers extras quando não há portfolio."""
        node = IngestPricesNode()
        ctx = PipelineContext()
        tickers = node._collect_tickers(ctx)

        # Deve ter benchmarks + commodities + crypto + FX
        assert "^BVSP" in tickers
        assert "CL=F" in tickers
        assert "BTC-USD" in tickers
        assert "BRL=X" in tickers

    def test_collect_tickers_com_portfolio(self, mock_portfolio):
        """Inclui tickers da carteira quando portfolio está no contexto."""
        node = IngestPricesNode()
        ctx = PipelineContext()
        ctx["portfolio"] = mock_portfolio
        tickers = node._collect_tickers(ctx)

        assert "PETR4.SA" in tickers
        assert "HGLG11.SA" in tickers
        assert "NTNB-2035" in tickers
        # Extras também presentes
        assert "^BVSP" in tickers

    def test_tickers_sorted(self):
        """Tickers retornados são ordenados."""
        node = IngestPricesNode()
        ctx = PipelineContext()
        tickers = node._collect_tickers(ctx)
        assert tickers == sorted(tickers)

    def test_mode_daily(self):
        """Inicializa com mode daily por default."""
        node = IngestPricesNode()
        assert node._mode == "daily"

    def test_mode_full(self):
        """Aceita mode full."""
        node = IngestPricesNode(mode="full")
        assert node._mode == "full"

    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher", autospec=True)
    def test_run_persiste_precos(self, MockFetcher, ctx_with_lake):
        """Run busca preços e persiste no lake."""
        # Simula retorno do fetcher
        dates = pd.date_range("2025-01-01", periods=3)
        df = pd.DataFrame(
            {"Close": [100, 101, 102], "Volume": [1000, 1100, 1200]},
            index=dates,
        )
        df.index.name = "Date"
        # Adiciona ticker como coluna para formato longo
        df["ticker"] = "^BVSP"

        mock_fetcher = MockFetcher.return_value
        mock_fetcher.get_historical_price_data.return_value = df

        node = IngestPricesNode(mode="daily")
        ctx = node.run(ctx_with_lake)

        assert "ingest_prices_count" in ctx
        assert ctx["ingest_prices_count"] >= 0

    @patch("carteira_auto.data.lake.DataLake")
    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher", autospec=True)
    def test_run_cria_lake_se_ausente(self, MockFetcher, MockLake):
        """Cria DataLake se não existir no contexto."""
        mock_fetcher = MockFetcher.return_value
        mock_fetcher.get_historical_price_data.return_value = None

        mock_lake = MockLake.return_value
        mock_lake.store_prices.return_value = 0

        node = IngestPricesNode()
        ctx = PipelineContext()
        ctx = node.run(ctx)

        assert "data_lake" in ctx

    def test_node_name(self):
        """Nome do node é correto."""
        node = IngestPricesNode()
        assert node.name == "ingest_prices"

    def test_no_dependencies(self):
        """Node não tem dependências."""
        node = IngestPricesNode()
        assert node.dependencies == []


# =============================================================================
# IngestMacroNode
# =============================================================================


class TestIngestMacroNode:
    """Testes para IngestMacroNode."""

    def test_node_name(self):
        node = IngestMacroNode()
        assert node.name == "ingest_macro"

    def test_no_dependencies(self):
        node = IngestMacroNode()
        assert node.dependencies == []

    @patch("carteira_auto.data.fetchers.BCBFetcher", autospec=True)
    def test_ingest_bcb(self, MockBCB, ctx_with_lake):
        """Ingere indicadores BCB no lake."""
        mock_fetcher = MockBCB.return_value
        # Simula retorno real do BCB: colunas 'data' e 'valor' com RangeIndex
        df = pd.DataFrame(
            {
                "data": pd.to_datetime(["2025-01-01", "2025-02-01"]),
                "valor": [13.75, 13.65],
            }
        )
        mock_fetcher.get_selic.return_value = df
        mock_fetcher.get_cdi.return_value = df
        mock_fetcher.get_ipca.return_value = df
        mock_fetcher.get_ptax.return_value = df

        node = IngestMacroNode()
        count = node._ingest_bcb(ctx_with_lake["data_lake"])
        # Deve inserir registros reais (4 indicadores × 2 datas = 8)
        assert count > 0

    @patch("carteira_auto.data.fetchers.IBGEFetcher", autospec=True)
    def test_ingest_ibge(self, MockIBGE, ctx_with_lake):
        """Ingere indicadores IBGE no lake."""
        mock_fetcher = MockIBGE.return_value
        # Simula retorno real do IBGE: colunas 'periodo' e 'valor' com RangeIndex
        # IBGE SIDRA retorna periodo como nome descritivo (ex: "janeiro 2025")
        # e opcionalmente periodo_codigo (ex: "202501")
        df = pd.DataFrame(
            {
                "periodo": ["janeiro 2025", "abril 2025"],
                "periodo_codigo": ["202501", "202504"],
                "valor": [1.5, 1.8],
            }
        )
        mock_fetcher.get_ipca.return_value = df
        mock_fetcher.get_pib.return_value = df

        node = IngestMacroNode()
        count = node._ingest_ibge(ctx_with_lake["data_lake"])
        # Deve inserir registros reais (2 indicadores × 2 datas = 4)
        assert count > 0

    @patch("carteira_auto.data.fetchers.IBGEFetcher", autospec=True)
    @patch("carteira_auto.data.fetchers.BCBFetcher", autospec=True)
    def test_run_produz_contexto(self, MockBCB, MockIBGE, ctx_with_lake):
        """Run popula ingest_macro_count no contexto."""
        # Mock BCB
        mock_bcb = MockBCB.return_value
        mock_bcb.get_selic.return_value = None
        mock_bcb.get_cdi.return_value = None
        mock_bcb.get_ipca.return_value = None
        mock_bcb.get_ptax.return_value = None
        # Mock IBGE
        mock_ibge = MockIBGE.return_value
        mock_ibge.get_ipca.return_value = None
        mock_ibge.get_pib.return_value = None

        node = IngestMacroNode()
        ctx = node.run(ctx_with_lake)

        assert "ingest_macro_count" in ctx
        assert ctx["ingest_macro_count"] == 0


# =============================================================================
# IngestFundamentalsNode
# =============================================================================


class TestIngestFundamentalsNode:
    """Testes para IngestFundamentalsNode."""

    def test_node_name(self):
        node = IngestFundamentalsNode()
        assert node.name == "ingest_fundamentals"

    def test_no_dependencies(self):
        node = IngestFundamentalsNode()
        assert node.dependencies == []

    def test_collect_tickers_sem_portfolio(self):
        """Retorna lista vazia sem portfolio no contexto."""
        node = IngestFundamentalsNode()
        ctx = PipelineContext()
        tickers = node._collect_tickers(ctx)
        assert tickers == []

    def test_collect_tickers_com_portfolio(self, mock_portfolio):
        """Filtra apenas ações e FIIs."""
        node = IngestFundamentalsNode()
        ctx = PipelineContext()
        ctx["portfolio"] = mock_portfolio
        tickers = node._collect_tickers(ctx)

        assert "PETR4.SA" in tickers
        assert "HGLG11.SA" in tickers
        # Renda Fixa não deve aparecer
        assert "NTNB-2035" not in tickers

    def test_collect_tickers_com_lista_explicita(self):
        """Usa lista explícita de tickers quando fornecida."""
        node = IngestFundamentalsNode(tickers=["VALE3.SA", "ITUB4.SA"])
        ctx = PipelineContext()
        tickers = node._collect_tickers(ctx)
        assert tickers == ["VALE3.SA", "ITUB4.SA"]

    def test_run_sem_tickers(self, ctx_with_lake):
        """Retorna 0 quando não há tickers para processar."""
        node = IngestFundamentalsNode()
        ctx = node.run(ctx_with_lake)

        assert ctx["ingest_fundamentals_count"] == 0

    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher", autospec=True)
    def test_run_com_tickers(self, MockFetcher, ctx_with_lake):
        """Busca e persiste fundamentos quando há tickers."""
        mock_fetcher = MockFetcher.return_value
        mock_fetcher.get_basic_info.return_value = {
            "trailingPE": 8.5,
            "priceToBook": 1.2,
            "returnOnEquity": 0.25,
            "dividendYield": 0.08,
        }
        mock_fetcher.get_financials.return_value = None

        node = IngestFundamentalsNode(tickers=["PETR4.SA"])
        ctx = node.run(ctx_with_lake)

        assert "ingest_fundamentals_count" in ctx
        assert ctx["ingest_fundamentals_count"] >= 0

    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher", autospec=True)
    def test_run_erro_no_fetcher_nao_quebra(self, MockFetcher, ctx_with_lake):
        """Erro em um ticker não impede o processamento dos demais."""
        mock_fetcher = MockFetcher.return_value
        mock_fetcher.get_basic_info.side_effect = Exception("API error")

        node = IngestFundamentalsNode(tickers=["PETR4.SA", "VALE3.SA"])
        ctx = node.run(ctx_with_lake)

        # Não deve lançar exceção
        assert ctx["ingest_fundamentals_count"] == 0


# =============================================================================
# IngestNewsNode
# =============================================================================


class TestIngestNewsNode:
    """Testes para IngestNewsNode."""

    def test_node_name(self):
        node = IngestNewsNode()
        assert node.name == "ingest_news"

    def test_no_dependencies(self):
        node = IngestNewsNode()
        assert node.dependencies == []

    def test_default_sources(self):
        """Sources default incluem ddm e newsapi."""
        node = IngestNewsNode()
        assert "ddm" in node._sources
        assert "newsapi" in node._sources

    def test_custom_sources(self):
        """Aceita fontes customizadas."""
        node = IngestNewsNode(sources=["rss", "newsapi"])
        assert node._sources == ["rss", "newsapi"]

    def test_run_sem_api_key(self, ctx_with_lake):
        """Retorna 0 quando API key não está configurada."""
        node = IngestNewsNode()
        ctx = node.run(ctx_with_lake)

        assert ctx["ingest_news_count"] == 0

    def test_run_fonte_desconhecida(self, ctx_with_lake):
        """Fonte desconhecida retorna 0 sem erro."""
        node = IngestNewsNode(sources=["fonte_inexistente"])
        ctx = node.run(ctx_with_lake)

        assert ctx["ingest_news_count"] == 0

    def test_fetch_rss_retorna_vazio(self):
        """RSS retorna lista vazia (ainda não implementado)."""
        node = IngestNewsNode()
        result = node._fetch_rss()
        assert result == []

    def test_fetch_newsapi_sem_key_retorna_vazio(self):
        """NewsAPI retorna lista vazia sem API key."""
        node = IngestNewsNode()
        result = node._fetch_newsapi()
        assert result == []
