"""Testes unitários para o DataLake SQLite.

Testa PriceLake, MacroLake, FundamentalsLake, NewsLake e DataLake (fachada).
Todos os testes usam SQLite em disco temporário (tmp_path do pytest).
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from carteira_auto.data.lake.base import DataLake
from carteira_auto.data.lake.fundamentals_lake import FundamentalsLake
from carteira_auto.data.lake.macro_lake import MacroLake
from carteira_auto.data.lake.news_lake import NewsLake
from carteira_auto.data.lake.price_lake import PriceLake

# ============================================================================
# PriceLake
# ============================================================================


class TestPriceLake:
    """Testes para PriceLake."""

    @pytest.fixture
    def lake(self, tmp_lake_dir: Path) -> PriceLake:
        return PriceLake(tmp_lake_dir / "prices.db")

    @pytest.fixture
    def sample_prices_long(self) -> pd.DataFrame:
        """DataFrame no formato long (ticker, date, close, ...)."""
        return pd.DataFrame(
            {
                "ticker": ["PETR4.SA", "PETR4.SA", "VALE3.SA", "VALE3.SA"],
                "date": ["2025-01-02", "2025-01-03", "2025-01-02", "2025-01-03"],
                "open": [30.0, 31.0, 60.0, 61.0],
                "high": [32.0, 33.0, 62.0, 63.0],
                "low": [29.0, 30.0, 59.0, 60.0],
                "close": [31.0, 32.0, 61.0, 62.0],
                "volume": [1000000, 1100000, 2000000, 2100000],
            }
        )

    @pytest.fixture
    def sample_prices_wide(self) -> pd.DataFrame:
        """DataFrame no formato wide (yfinance simples)."""
        dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
        return pd.DataFrame(
            {"PETR4.SA": [31.0, 32.0], "VALE3.SA": [61.0, 62.0]},
            index=dates,
        )

    def test_store_long_format(self, lake: PriceLake, sample_prices_long: pd.DataFrame):
        """Armazena preços no formato long."""
        count = lake.store(sample_prices_long, source="yahoo")
        assert count == 4
        assert lake.count_records() == 4

    def test_store_wide_format(self, lake: PriceLake, sample_prices_wide: pd.DataFrame):
        """Armazena preços no formato wide (colunas = tickers)."""
        count = lake.store(sample_prices_wide, source="yahoo")
        assert count == 4
        assert lake.count_records() == 4

    def test_store_empty_df(self, lake: PriceLake):
        """DataFrame vazio retorna 0."""
        count = lake.store(pd.DataFrame(), source="yahoo")
        assert count == 0

    def test_store_upsert(self, lake: PriceLake, sample_prices_long: pd.DataFrame):
        """Upsert não duplica registros."""
        lake.store(sample_prices_long, source="yahoo")
        lake.store(sample_prices_long, source="yahoo")
        assert lake.count_records() == 4

    def test_get_prices(self, lake: PriceLake, sample_prices_long: pd.DataFrame):
        """Consulta preços no formato wide."""
        lake.store(sample_prices_long, source="yahoo")
        result = lake.get_prices(["PETR4.SA", "VALE3.SA"])

        assert not result.empty
        assert "PETR4.SA" in result.columns
        assert "VALE3.SA" in result.columns
        assert len(result) == 2

    def test_get_prices_with_date_range(
        self, lake: PriceLake, sample_prices_long: pd.DataFrame
    ):
        """Consulta preços com filtro de data."""
        lake.store(sample_prices_long, source="yahoo")
        result = lake.get_prices(
            ["PETR4.SA"],
            start=date(2025, 1, 3),
            end=date(2025, 1, 3),
        )
        assert len(result) == 1
        assert result["PETR4.SA"].iloc[0] == 32.0

    def test_get_prices_empty(self, lake: PriceLake):
        """Consulta sem dados retorna DataFrame vazio."""
        result = lake.get_prices(["INEXISTENTE"])
        assert result.empty

    def test_get_latest_prices(self, lake: PriceLake, sample_prices_long: pd.DataFrame):
        """Retorna último preço de cada ticker."""
        lake.store(sample_prices_long, source="yahoo")
        latest = lake.get_latest_prices(["PETR4.SA", "VALE3.SA"])

        assert latest["PETR4.SA"] == 32.0
        assert latest["VALE3.SA"] == 62.0

    def test_get_available_tickers(
        self, lake: PriceLake, sample_prices_long: pd.DataFrame
    ):
        """Lista tickers disponíveis."""
        lake.store(sample_prices_long, source="yahoo")
        tickers = lake.get_available_tickers()
        assert set(tickers) == {"PETR4.SA", "VALE3.SA"}

    def test_get_date_range(self, lake: PriceLake, sample_prices_long: pd.DataFrame):
        """Range de datas disponível."""
        lake.store(sample_prices_long, source="yahoo")
        start, end = lake.get_date_range("PETR4.SA")
        assert start == date(2025, 1, 2)
        assert end == date(2025, 1, 3)

    def test_delete_ticker(self, lake: PriceLake, sample_prices_long: pd.DataFrame):
        """Remove dados de um ticker."""
        lake.store(sample_prices_long, source="yahoo")
        deleted = lake.delete_ticker("PETR4.SA")
        assert deleted == 2
        assert lake.count_records() == 2
        assert "PETR4.SA" not in lake.get_available_tickers()

    def test_export_to_parquet(
        self, lake: PriceLake, sample_prices_long: pd.DataFrame, tmp_lake_dir: Path
    ):
        """Exporta para Parquet."""
        lake.store(sample_prices_long, source="yahoo")
        output = tmp_lake_dir / "prices.parquet"
        result_path = lake.export_to_parquet(output)

        assert result_path.exists()
        df = pd.read_parquet(result_path)
        assert len(df) == 4

    def test_get_prices_multiple_columns(
        self, lake: PriceLake, sample_prices_long: pd.DataFrame
    ):
        """Consulta múltiplas colunas OHLCV."""
        lake.store(sample_prices_long, source="yahoo")
        result = lake.get_prices(["PETR4.SA"], columns=["open", "close"])
        assert not result.empty


# ============================================================================
# MacroLake
# ============================================================================


class TestMacroLake:
    """Testes para MacroLake."""

    @pytest.fixture
    def lake(self, tmp_lake_dir: Path) -> MacroLake:
        return MacroLake(tmp_lake_dir / "macro.db")

    @pytest.fixture
    def sample_selic(self) -> pd.DataFrame:
        """Série de SELIC simulada."""
        dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
        return pd.DataFrame({"value": [14.25, 14.25, 14.25]}, index=dates)

    def test_store_indicator(self, lake: MacroLake, sample_selic: pd.DataFrame):
        """Armazena indicador macro."""
        count = lake.store(
            "selic", sample_selic, source="bcb", unit="%", frequency="daily"
        )
        assert count == 3
        assert lake.count_records() == 3

    def test_store_with_date_column(self, lake: MacroLake):
        """Armazena DataFrame com coluna 'date' explícita."""
        df = pd.DataFrame(
            {
                "date": ["2025-01-02", "2025-01-03"],
                "value": [14.25, 14.50],
            }
        )
        count = lake.store("selic", df, source="bcb")
        assert count == 2

    def test_get_indicator(self, lake: MacroLake, sample_selic: pd.DataFrame):
        """Consulta série de indicador."""
        lake.store("selic", sample_selic, source="bcb")
        result = lake.get_indicator("selic")

        assert not result.empty
        assert "value" in result.columns
        assert len(result) == 3

    def test_get_indicator_with_range(
        self, lake: MacroLake, sample_selic: pd.DataFrame
    ):
        """Consulta com filtro de data."""
        lake.store("selic", sample_selic, source="bcb")
        result = lake.get_indicator("selic", start=date(2025, 1, 3))
        assert len(result) == 2

    def test_get_multiple_indicators(self, lake: MacroLake):
        """Consulta múltiplos indicadores em formato wide."""
        dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
        selic = pd.DataFrame({"value": [14.25, 14.25]}, index=dates)
        ipca = pd.DataFrame({"value": [4.5, 4.6]}, index=dates)

        lake.store("selic", selic, source="bcb")
        lake.store("ipca", ipca, source="bcb")

        result = lake.get_multiple_indicators(["selic", "ipca"])
        assert "selic" in result.columns
        assert "ipca" in result.columns
        assert len(result) == 2

    def test_get_latest_value(self, lake: MacroLake, sample_selic: pd.DataFrame):
        """Retorna último valor."""
        lake.store("selic", sample_selic, source="bcb")
        latest = lake.get_latest_value("selic")
        assert latest == 14.25

    def test_get_available_indicators(
        self, lake: MacroLake, sample_selic: pd.DataFrame
    ):
        """Lista indicadores com metadados."""
        lake.store("selic", sample_selic, source="bcb", unit="%")
        indicators = lake.get_available_indicators()
        assert len(indicators) == 1
        assert indicators[0]["indicator"] == "selic"
        assert indicators[0]["unit"] == "%"

    def test_export_to_parquet(
        self, lake: MacroLake, sample_selic: pd.DataFrame, tmp_lake_dir: Path
    ):
        """Exporta para Parquet."""
        lake.store("selic", sample_selic, source="bcb")
        output = tmp_lake_dir / "macro.parquet"
        result_path = lake.export_to_parquet(output)
        assert result_path.exists()


# ============================================================================
# FundamentalsLake
# ============================================================================


class TestFundamentalsLake:
    """Testes para FundamentalsLake."""

    @pytest.fixture
    def lake(self, tmp_lake_dir: Path) -> FundamentalsLake:
        return FundamentalsLake(tmp_lake_dir / "fundamentals.db")

    def test_store_indicators(self, lake: FundamentalsLake):
        """Armazena indicadores fundamentalistas."""
        indicators = {"pl": 5.2, "pvp": 0.8, "roe": 0.25, "dy": 0.08}
        count = lake.store_indicators("PETR4", "2025-Q3", indicators, "cvm")
        assert count == 4

    def test_store_statement(self, lake: FundamentalsLake):
        """Armazena demonstração financeira."""
        data = {"receita_liquida": 100000, "lucro_liquido": 25000}
        lake.store_statement("PETR4", "2025-Q3", "dre", data, "cvm")

        result = lake.get_statement("PETR4", "2025-Q3", "dre")
        assert result is not None
        assert result["receita_liquida"] == 100000

    def test_get_indicators(self, lake: FundamentalsLake):
        """Consulta indicadores de um ticker."""
        lake.store_indicators("PETR4", "2025-Q1", {"pl": 5.0, "pvp": 0.7}, "cvm")
        lake.store_indicators("PETR4", "2025-Q2", {"pl": 5.1, "pvp": 0.75}, "cvm")
        lake.store_indicators("PETR4", "2025-Q3", {"pl": 5.2, "pvp": 0.8}, "cvm")

        result = lake.get_indicators("PETR4", periods=2)
        assert len(result) == 2
        assert "pl" in result.columns
        assert "pvp" in result.columns

    def test_get_indicator_for_tickers(self, lake: FundamentalsLake):
        """Consulta indicador para múltiplos tickers."""
        lake.store_indicators("PETR4", "2025-Q3", {"pl": 5.2}, "cvm")
        lake.store_indicators("VALE3", "2025-Q3", {"pl": 8.1}, "cvm")

        result = lake.get_indicator_for_tickers(["PETR4", "VALE3"], "pl")
        assert "PETR4" in result.index
        assert "VALE3" in result.index

    def test_get_available_tickers(self, lake: FundamentalsLake):
        """Lista tickers disponíveis."""
        lake.store_indicators("PETR4", "2025-Q3", {"pl": 5.2}, "cvm")
        lake.store_indicators("VALE3", "2025-Q3", {"pl": 8.1}, "cvm")
        tickers = lake.get_available_tickers()
        assert set(tickers) == {"PETR4", "VALE3"}

    def test_export_to_parquet(self, lake: FundamentalsLake, tmp_lake_dir: Path):
        """Exporta para Parquet."""
        lake.store_indicators("PETR4", "2025-Q3", {"pl": 5.2}, "cvm")
        output = tmp_lake_dir / "fundamentals.parquet"
        result_path = lake.export_to_parquet(output)
        assert result_path.exists()


# ============================================================================
# NewsLake
# ============================================================================


class TestNewsLake:
    """Testes para NewsLake."""

    @pytest.fixture
    def lake(self, tmp_lake_dir: Path) -> NewsLake:
        return NewsLake(tmp_lake_dir / "news.db")

    @pytest.fixture
    def sample_articles(self) -> list[dict]:
        return [
            {
                "title": "PETR4 sobe 5% após resultados trimestrais",
                "description": "Petrobras reporta lucro acima do esperado",
                "url": "https://example.com/1",
                "published_at": "2025-01-15T10:00:00",
                "category": "mercado",
                "tickers": ["PETR4"],
                "sentiment_score": 0.8,
                "sentiment_label": "positive",
            },
            {
                "title": "Selic mantida em 14.25%",
                "description": "Copom decide manter taxa básica",
                "url": "https://example.com/2",
                "published_at": "2025-01-15T15:00:00",
                "category": "macro",
                "tickers": [],
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
            },
        ]

    def test_store_articles(self, lake: NewsLake, sample_articles: list[dict]):
        """Armazena artigos."""
        lake.store(sample_articles, source="newsapi")
        assert lake.count_records() >= 2

    def test_store_ignores_duplicates(
        self, lake: NewsLake, sample_articles: list[dict]
    ):
        """Duplicatas são ignoradas (UNIQUE constraint)."""
        lake.store(sample_articles, source="newsapi")
        lake.store(sample_articles, source="newsapi")
        assert lake.count_records() == 2

    def test_get_news(self, lake: NewsLake, sample_articles: list[dict]):
        """Consulta notícias."""
        lake.store(sample_articles, source="newsapi")
        result = lake.get_news()
        assert len(result) == 2

    def test_get_news_by_category(self, lake: NewsLake, sample_articles: list[dict]):
        """Filtra por categoria."""
        lake.store(sample_articles, source="newsapi")
        result = lake.get_news(category="macro")
        assert len(result) == 1
        assert "Selic" in result.iloc[0]["title"]

    def test_get_news_by_ticker(self, lake: NewsLake, sample_articles: list[dict]):
        """Filtra por ticker mencionado."""
        lake.store(sample_articles, source="newsapi")
        result = lake.get_news(ticker="PETR4")
        assert len(result) == 1

    def test_update_sentiment(self, lake: NewsLake, sample_articles: list[dict]):
        """Atualiza sentimento de artigo."""
        lake.store(sample_articles, source="newsapi")
        # Busca primeiro artigo
        news = lake.get_news(limit=1)
        article_id = news.iloc[0]["id"]
        lake.update_sentiment(article_id, score=-0.5, label="negative")

    def test_get_sentiment_series(self, lake: NewsLake, sample_articles: list[dict]):
        """Série temporal de sentimento."""
        lake.store(sample_articles, source="newsapi")
        result = lake.get_sentiment_series()
        assert not result.empty
        assert "mean_sentiment" in result.columns

    def test_get_unscored_articles(self, lake: NewsLake):
        """Artigos sem score de sentimento."""
        articles = [
            {"title": "Notícia sem score", "published_at": "2025-01-15T10:00:00"},
        ]
        lake.store(articles, source="test")
        unscored = lake.get_unscored_articles()
        assert len(unscored) == 1

    def test_export_to_parquet(
        self, lake: NewsLake, sample_articles: list[dict], tmp_lake_dir: Path
    ):
        """Exporta para Parquet."""
        lake.store(sample_articles, source="newsapi")
        output = tmp_lake_dir / "news.parquet"
        result_path = lake.export_to_parquet(output)
        assert result_path.exists()


# ============================================================================
# DataLake (fachada)
# ============================================================================


class TestDataLake:
    """Testes para DataLake (interface unificada)."""

    @pytest.fixture
    def lake(self, tmp_lake_dir: Path) -> DataLake:
        return DataLake(tmp_lake_dir)

    def test_initialization(self, lake: DataLake):
        """DataLake inicializa todos os sub-lakes."""
        assert lake.prices is not None
        assert lake.macro is not None
        assert lake.fundamentals is not None
        assert lake.news is not None

    def test_store_and_get_prices(self, lake: DataLake):
        """Armazena e consulta preços via fachada."""
        df = pd.DataFrame(
            {
                "ticker": ["PETR4.SA", "PETR4.SA"],
                "date": ["2025-01-02", "2025-01-03"],
                "close": [31.0, 32.0],
            }
        )
        lake.store_prices(df, source="yahoo")
        result = lake.get_prices(["PETR4.SA"])
        assert not result.empty

    def test_store_and_get_macro(self, lake: DataLake):
        """Armazena e consulta indicador macro via fachada."""
        df = pd.DataFrame(
            {"value": [14.25, 14.25]},
            index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
        )
        lake.store_macro("selic", df, source="bcb", unit="%")
        result = lake.get_macro("selic")
        assert not result.empty

    def test_store_and_get_fundamentals(self, lake: DataLake):
        """Armazena e consulta fundamentos via fachada."""
        lake.store_fundamentals("PETR4", "2025-Q3", {"pl": 5.2}, "cvm")
        result = lake.get_fundamentals("PETR4")
        assert not result.empty

    def test_store_and_get_news(self, lake: DataLake):
        """Armazena e consulta notícias via fachada."""
        articles = [
            {"title": "Teste", "published_at": "2025-01-15T10:00:00"},
        ]
        lake.store_news(articles, source="test")
        result = lake.get_news()
        assert len(result) == 1

    def test_summary(self, lake: DataLake):
        """Resumo do data lake."""
        summary = lake.summary()
        assert "prices" in summary
        assert "macro" in summary
        assert "fundamentals" in summary
        assert "news" in summary
        assert "lake_dir" in summary

    def test_get_latest_prices(self, lake: DataLake):
        """Último preço via fachada."""
        df = pd.DataFrame(
            {
                "ticker": ["PETR4.SA"],
                "date": ["2025-01-03"],
                "close": [32.0],
            }
        )
        lake.store_prices(df)
        latest = lake.get_latest_prices(["PETR4.SA"])
        assert latest["PETR4.SA"] == 32.0

    def test_get_macro_latest(self, lake: DataLake):
        """Último valor macro via fachada."""
        df = pd.DataFrame(
            {"value": [14.25]},
            index=pd.to_datetime(["2025-01-02"]),
        )
        lake.store_macro("selic", df, source="bcb")
        assert lake.get_macro_latest("selic") == 14.25

    def test_export_all_to_parquet(self, lake: DataLake):
        """Exporta todos os sub-lakes."""
        # Insere dados mínimos
        df_prices = pd.DataFrame(
            {
                "ticker": ["PETR4.SA"],
                "date": ["2025-01-02"],
                "close": [31.0],
            }
        )
        lake.store_prices(df_prices)

        df_macro = pd.DataFrame(
            {"value": [14.25]},
            index=pd.to_datetime(["2025-01-02"]),
        )
        lake.store_macro("selic", df_macro, source="bcb")

        results = lake.export_all_to_parquet()
        assert "prices" in results
        assert results["prices"].exists()
