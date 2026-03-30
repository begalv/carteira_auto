"""DataLake — interface unificada para persistência de séries temporais.

Agrega PriceLake, MacroLake, FundamentalsLake e NewsLake em uma única
fachada, simplificando o acesso aos dados para analyzers e estratégias.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from carteira_auto.data.lake.fundamentals_lake import FundamentalsLake
from carteira_auto.data.lake.macro_lake import MacroLake
from carteira_auto.data.lake.news_lake import NewsLake
from carteira_auto.data.lake.price_lake import PriceLake
from carteira_auto.data.lake.reference_lake import ReferenceLake
from carteira_auto.utils.logger import get_logger

logger = get_logger(__name__)


class DataLake:
    """Interface unificada para o data lake financeiro.

    Agrega todos os sub-lakes (prices, macro, fundamentals, news) em
    uma única interface. Cada sub-lake gerencia seu próprio arquivo
    SQLite, garantindo isolamento e performance.

    Uso:
        lake = DataLake(Path("data/lake"))
        lake.store_prices(df, source="yahoo")
        prices = lake.get_prices(["PETR4.SA"], start, end)
        selic = lake.get_macro("selic", start, end)
    """

    def __init__(self, lake_dir: Path) -> None:
        self._lake_dir = lake_dir
        self._lake_dir.mkdir(parents=True, exist_ok=True)
        self._parquet_dir = lake_dir / "parquet"

        # Sub-lakes
        self.prices = PriceLake(lake_dir / "prices.db")
        self.macro = MacroLake(lake_dir / "macro.db")
        self.fundamentals = FundamentalsLake(lake_dir / "fundamentals.db")
        self.news = NewsLake(lake_dir / "news.db")
        self.reference = ReferenceLake(lake_dir / "reference.db")

        logger.debug(f"DataLake inicializado em {lake_dir}")

    # ================================================================
    # PREÇOS
    # ================================================================

    def store_prices(self, df: pd.DataFrame, source: str = "yahoo") -> int:
        """Persiste preços OHLCV no lake."""
        return self.prices.store(df, source)

    def get_prices(
        self,
        tickers: list[str],
        start: date | None = None,
        end: date | None = None,
        columns: list[str] | None = None,
        lookback: int | None = None,
    ) -> pd.DataFrame:
        """Consulta preços do lake.

        Args:
            tickers: Lista de tickers.
            start: Data inicial.
            end: Data final.
            columns: Colunas desejadas (default: ["close"]).
            lookback: Se fornecido, ignora start/end e retorna os últimos
                      N dias úteis a partir de hoje.

        Returns:
            DataFrame wide com DatetimeIndex e colunas por ticker.
        """
        if lookback:
            end = end or date.today()
            # Estima start com margem (weekends/feriados)
            import datetime as dt

            start = end - dt.timedelta(days=int(lookback * 1.5))

        return self.prices.get_prices(tickers, start, end, columns)

    def get_latest_prices(self, tickers: list[str]) -> dict[str, float]:
        """Retorna último preço de fechamento de cada ticker."""
        return self.prices.get_latest_prices(tickers)

    # ================================================================
    # MACRO
    # ================================================================

    def store_macro(
        self,
        indicator: str,
        df: pd.DataFrame,
        source: str,
        unit: str = "",
        frequency: str = "daily",
    ) -> int:
        """Persiste série de indicador macro."""
        return self.macro.store(indicator, df, source, unit, frequency)

    def get_macro(
        self,
        indicator: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Consulta série de indicador macro."""
        return self.macro.get_indicator(indicator, start, end)

    def get_macro_latest(self, indicator: str) -> float | None:
        """Retorna último valor de um indicador macro."""
        return self.macro.get_latest_value(indicator)

    # ================================================================
    # FUNDAMENTOS
    # ================================================================

    def store_fundamentals(
        self,
        ticker: str,
        period: str,
        indicators: dict[str, float],
        source: str,
    ) -> int:
        """Persiste indicadores fundamentalistas."""
        return self.fundamentals.store_indicators(ticker, period, indicators, source)

    def store_statement(
        self,
        ticker: str,
        period: str,
        statement_type: str,
        data: dict[str, Any],
        source: str,
    ) -> None:
        """Persiste demonstração financeira (DRE, Balanço, DFC)."""
        self.fundamentals.store_statement(ticker, period, statement_type, data, source)

    def get_fundamentals(
        self,
        ticker: str,
        periods: int = 8,
        indicators: list[str] | None = None,
    ) -> pd.DataFrame:
        """Consulta indicadores fundamentalistas de um ticker."""
        return self.fundamentals.get_indicators(ticker, periods, indicators)

    # ================================================================
    # NOTÍCIAS
    # ================================================================

    def store_news(self, articles: list[dict], source: str) -> int:
        """Persiste artigos/headlines."""
        return self.news.store(articles, source)

    def get_news(
        self,
        start: date | None = None,
        end: date | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Consulta notícias do lake."""
        return self.news.get_news(start, end, category, limit=limit)

    def get_sentiment(
        self,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Retorna série temporal de sentimento agregado."""
        return self.news.get_sentiment_series(start, end)

    # ================================================================
    # REFERÊNCIA (composição de índices, Focus, targets, etc.)
    # ================================================================

    def store_index_composition(
        self,
        index_code: str,
        df: pd.DataFrame,
        source: str,
        ref_date: str | None = None,
    ) -> int:
        """Persiste composição de um índice."""
        return self.reference.store_index_composition(index_code, df, source, ref_date)

    def get_index_composition(
        self,
        index_code: str,
        ref_date: str | None = None,
    ) -> pd.DataFrame:
        """Consulta composição de um índice."""
        return self.reference.get_index_composition(index_code, ref_date)

    def store_focus_expectations(
        self,
        indicator: str,
        data: list[dict] | pd.DataFrame,
        source: str = "bcb",
    ) -> int:
        """Persiste expectativas Focus do BCB."""
        return self.reference.store_focus_expectations(indicator, data, source)

    def store_analyst_targets(
        self,
        ticker: str,
        targets: dict,
        source: str = "yahoo",
    ) -> int:
        """Persiste targets de preço de analistas."""
        return self.reference.store_analyst_targets(ticker, targets, source)

    def store_ticker_cnpj(
        self,
        mapping: dict[str, dict],
        source: str,
    ) -> int:
        """Persiste mapeamento ticker → CNPJ."""
        return self.reference.store_ticker_cnpj(mapping, source)

    def store_major_holders(
        self,
        ticker: str,
        holders: dict,
        source: str = "yahoo",
    ) -> int:
        """Persiste participação acionária (major holders) de um ticker."""
        return self.reference.store_major_holders(ticker, holders, source)

    def store_fund_registry(
        self,
        funds: list | pd.DataFrame,
        source: str = "cvm",
    ) -> int:
        """Persiste cadastro de fundos e FIIs."""
        return self.reference.store_fund_registry(funds, source)

    def store_fund_portfolios(
        self,
        cnpj: str,
        df: pd.DataFrame,
        source: str = "cvm",
        ref_date: str | None = None,
    ) -> int:
        """Persiste composição de carteira de um fundo (CDA)."""
        return self.reference.store_fund_portfolios(cnpj, df, source, ref_date)

    def store_intermediaries(
        self,
        intermediaries: list | pd.DataFrame,
        source: str = "cvm",
    ) -> int:
        """Persiste cadastro de intermediários (corretoras/distribuidoras)."""
        return self.reference.store_intermediaries(intermediaries, source)

    def store_asset_registry(
        self,
        assets: list | pd.DataFrame,
        asset_type: str,
        source: str = "tradingcomdados",
    ) -> int:
        """Persiste lista de ativos por tipo (stock, fii, bdr, etf)."""
        return self.reference.store_asset_registry(assets, asset_type, source)

    # ================================================================
    # EXPORTAÇÃO
    # ================================================================

    def export_all_to_parquet(self) -> dict[str, Path]:
        """Exporta todos os sub-lakes para Parquet.

        Returns:
            Dict {nome_lake: caminho_parquet}.
        """
        self._parquet_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        results["prices"] = self.prices.export_to_parquet(
            self._parquet_dir / "prices.parquet"
        )
        results["macro"] = self.macro.export_to_parquet(
            self._parquet_dir / "macro.parquet"
        )
        results["fundamentals"] = self.fundamentals.export_to_parquet(
            self._parquet_dir / "fundamentals.parquet"
        )
        results["news"] = self.news.export_to_parquet(
            self._parquet_dir / "news.parquet"
        )
        results["reference"] = self.reference.export_to_parquet(
            self._parquet_dir / "reference.parquet"
        )

        logger.info(f"DataLake: todos os dados exportados para {self._parquet_dir}")
        return results

    # ================================================================
    # INFORMAÇÕES
    # ================================================================

    def summary(self) -> dict[str, Any]:
        """Retorna resumo do estado do data lake.

        Returns:
            Dict com contagem de registros e tickers por sub-lake.
        """
        return {
            "prices": {
                "records": self.prices.count_records(),
                "tickers": len(self.prices.get_available_tickers()),
            },
            "macro": {
                "records": self.macro.count_records(),
                "indicators": len(self.macro.get_available_indicators()),
            },
            "fundamentals": {
                "records": self.fundamentals.count_records(),
                "tickers": len(self.fundamentals.get_available_tickers()),
            },
            "news": {
                "records": self.news.count_records(),
            },
            "reference": self.reference.count_records(),
            "lake_dir": str(self._lake_dir),
        }
