"""Nodes de ingestão — buscam dados de fetchers e persistem no DataLake.

Responsáveis por alimentar o DataLake com dados de preços, indicadores
macro, fundamentos e notícias. Separação clara: fetchers buscam,
IngestNodes orquestram a persistência.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from carteira_auto.config import settings
from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class IngestPricesNode(Node):
    """Busca preços históricos e persiste no DataLake.

    Busca preços OHLCV de todos os ativos da carteira + benchmarks +
    commodities via YahooFinanceFetcher e persiste no PriceLake.

    Lê do contexto (opcional):
        - "portfolio": Portfolio (se disponível, usa tickers da carteira)

    Produz no contexto:
        - "ingest_prices_count": int (registros persistidos)
        - "data_lake": DataLake (referência para nodes seguintes)

    Modos:
        - full: backfill histórico completo (default_lookback_years)
        - daily: apenas dados do último dia útil
    """

    name = "ingest_prices"
    dependencies: list[str] = []

    # Tickers adicionais além da carteira (benchmarks, commodities, crypto)
    BENCHMARK_TICKERS = [
        "^BVSP",  # IBOV
        "^GSPC",  # S&P 500
        "^IXIC",  # Nasdaq
    ]

    COMMODITY_TICKERS = [
        "CL=F",  # Petróleo WTI
        "GC=F",  # Ouro
        "SI=F",  # Prata
        "ZS=F",  # Soja
    ]

    CRYPTO_TICKERS = [
        "BTC-USD",
        "ETH-USD",
    ]

    FX_TICKERS = [
        "BRL=X",  # USD/BRL
        "EURBRL=X",  # EUR/BRL
        "DX-Y.NYB",  # DXY
    ]

    def __init__(self, mode: str = "daily", lookback_years: int | None = None):
        self._mode = mode
        self._lookback_years = lookback_years or settings.lake.DEFAULT_LOOKBACK_YEARS

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.fetchers import YahooFinanceFetcher
        from carteira_auto.data.lake import DataLake

        lake = ctx.get("data_lake") or DataLake(settings.paths.LAKE_DIR)
        ctx["data_lake"] = lake

        # Coleta tickers da carteira + extras
        tickers = self._collect_tickers(ctx)
        logger.info(f"IngestPrices ({self._mode}): {len(tickers)} tickers a processar")

        # Define período
        if self._mode == "full":
            period_str = f"{self._lookback_years}y"
        else:
            # Daily: últimos 5 dias (margem para weekends/feriados)
            period_str = "5d"

        # Busca preços via Yahoo
        fetcher = YahooFinanceFetcher()
        total_count = 0

        # Processa em lotes para evitar timeout
        batch_size = 20
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            try:
                df = fetcher.get_historical_price_data(batch, period=period_str)
                if df is not None and not df.empty:
                    count = lake.store_prices(df, source="yahoo")
                    total_count += count
                    logger.debug(f"  Lote {i // batch_size + 1}: {count} registros")
            except Exception as e:
                logger.warning(f"Erro ao buscar lote {batch[:3]}...: {e}")

        ctx["ingest_prices_count"] = total_count
        logger.info(f"IngestPrices: {total_count} registros persistidos no lake")
        return ctx

    def _collect_tickers(self, ctx: PipelineContext) -> list[str]:
        """Coleta tickers da carteira + benchmarks + commodities + crypto."""
        tickers: set[str] = set()

        # Tickers da carteira (se disponível no contexto)
        portfolio = ctx.get("portfolio")
        if portfolio:
            for asset in portfolio.assets:
                tickers.add(asset.ticker)

        # Extras
        tickers.update(self.BENCHMARK_TICKERS)
        tickers.update(self.COMMODITY_TICKERS)
        tickers.update(self.CRYPTO_TICKERS)
        tickers.update(self.FX_TICKERS)

        return sorted(tickers)


class IngestMacroNode(Node):
    """Busca indicadores macroeconômicos e persiste no DataLake.

    Busca indicadores do BCB (Selic, CDI, IPCA, PTAX, etc.) e do IBGE
    (PIB, IPCA detalhado) e persiste no MacroLake.

    Produz no contexto:
        - "ingest_macro_count": int (registros persistidos)
        - "data_lake": DataLake
    """

    name = "ingest_macro"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.lake import DataLake

        lake = ctx.get("data_lake") or DataLake(settings.paths.LAKE_DIR)
        ctx["data_lake"] = lake

        total_count = 0

        # --- BCB ---
        total_count += self._ingest_bcb(lake)

        # --- IBGE ---
        total_count += self._ingest_ibge(lake)

        ctx["ingest_macro_count"] = total_count
        logger.info(f"IngestMacro: {total_count} registros persistidos no lake")
        return ctx

    def _ingest_bcb(self, lake) -> int:
        """Ingere indicadores do BCB."""
        from carteira_auto.data.fetchers import BCBFetcher

        fetcher = BCBFetcher()
        count = 0

        # Indicadores BCB disponíveis no fetcher
        # BCBFetcher retorna DataFrames com colunas 'data' e 'valor'
        bcb_indicators = {
            "selic": ("get_selic", "%", "daily"),
            "cdi": ("get_cdi", "%", "daily"),
            "ipca": ("get_ipca", "%", "monthly"),
            "ptax": ("get_ptax", "R$/USD", "daily"),
        }

        for name, (method_name, unit, frequency) in bcb_indicators.items():
            try:
                method = getattr(fetcher, method_name)
                df = method()

                if df is not None and not df.empty:
                    # BCBFetcher retorna colunas 'data'/'valor' — normaliza para 'date'/'value'
                    df = self._normalize_bcb_df(df)
                    stored = lake.store_macro(
                        name, df, source="bcb", unit=unit, frequency=frequency
                    )
                    count += stored
                    logger.debug(f"  BCB/{name}: {stored} registros")
            except Exception as e:
                logger.warning(f"Erro ao buscar BCB/{name}: {e}")

        return count

    @staticmethod
    def _normalize_bcb_df(df) -> pd.DataFrame:
        """Normaliza DataFrame do BCBFetcher (colunas 'data'/'valor') para formato do MacroLake."""
        result = pd.DataFrame()
        if "data" in df.columns and "valor" in df.columns:
            result["date"] = pd.to_datetime(df["data"])
            result["value"] = pd.to_numeric(df["valor"], errors="coerce")
        elif "valor" in df.columns:
            # Caso tenha DatetimeIndex
            result["date"] = df.index
            result["value"] = df["valor"].values
        else:
            return df
        return result.dropna(subset=["value"])

    def _ingest_ibge(self, lake) -> int:
        """Ingere indicadores do IBGE."""
        from carteira_auto.data.fetchers import IBGEFetcher

        fetcher = IBGEFetcher()
        count = 0

        ibge_indicators = {
            "ipca_ibge": ("get_ipca", "%", "monthly"),
            "pib": ("get_pib", "R$ milhões", "quarterly"),
        }

        for name, (method_name, unit, frequency) in ibge_indicators.items():
            try:
                method = getattr(fetcher, method_name)
                df = method()
                if df is not None and not df.empty:
                    # IBGEFetcher retorna colunas 'periodo'/'valor' — normaliza
                    df = self._normalize_ibge_df(df)
                    stored = lake.store_macro(
                        name, df, source="ibge", unit=unit, frequency=frequency
                    )
                    count += stored
                    logger.debug(f"  IBGE/{name}: {stored} registros")
            except Exception as e:
                logger.warning(f"Erro ao buscar IBGE/{name}: {e}")

        return count

    @staticmethod
    def _normalize_ibge_df(df) -> pd.DataFrame:
        """Normaliza DataFrame do IBGEFetcher (colunas 'periodo'/'valor') para formato do MacroLake."""
        result = pd.DataFrame()
        if "valor" in df.columns:
            result["value"] = pd.to_numeric(df["valor"], errors="coerce")

            # Determina coluna de data: prefere periodo_codigo (YYYYMM) sobre periodo (nome)
            if "periodo_codigo" in df.columns:
                result["date"] = pd.to_datetime(
                    df["periodo_codigo"].astype(str), format="%Y%m", errors="coerce"
                )
            elif "periodo" in df.columns:
                # Tenta interpretar formato numérico (YYYYMM) ou textual
                periodo = df["periodo"].astype(str)
                result["date"] = pd.to_datetime(periodo, format="%Y%m", errors="coerce")
                # Fallback: formato misto
                mask = result["date"].isna()
                if mask.any():
                    result.loc[mask, "date"] = pd.to_datetime(
                        periodo[mask], format="mixed", dayfirst=True, errors="coerce"
                    )
            else:
                result["date"] = df.index
        else:
            return df
        return result.dropna(subset=["value", "date"])


class IngestFundamentalsNode(Node):
    """Busca dados fundamentalistas e persiste no DataLake.

    Busca indicadores fundamentalistas (P/L, P/VP, ROE, DY, etc.) e
    demonstrações financeiras via YahooFinanceFetcher e persiste no
    FundamentalsLake.

    Quando CVMFetcher estiver disponível (Fase 1), será a fonte primária
    com Yahoo como fallback.

    Lê do contexto (opcional):
        - "portfolio": Portfolio (se disponível, usa tickers de ações/FIIs)

    Produz no contexto:
        - "ingest_fundamentals_count": int (registros persistidos)
        - "data_lake": DataLake
    """

    name = "ingest_fundamentals"
    dependencies: list[str] = []

    # Indicadores a extrair do Yahoo info
    YAHOO_INDICATORS = [
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "returnOnEquity",
        "returnOnAssets",
        "debtToEquity",
        "currentRatio",
        "grossMargins",
        "operatingMargins",
        "profitMargins",
        "dividendYield",
        "payoutRatio",
        "earningsGrowth",
        "revenueGrowth",
        "enterpriseToEbitda",
        "marketCap",
        "totalRevenue",
        "netIncomeToCommon",
        "freeCashflow",
        "totalDebt",
    ]

    def __init__(self, tickers: list[str] | None = None):
        self._tickers = tickers

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.fetchers import YahooFinanceFetcher
        from carteira_auto.data.lake import DataLake

        lake = ctx.get("data_lake") or DataLake(settings.paths.LAKE_DIR)
        ctx["data_lake"] = lake

        tickers = self._collect_tickers(ctx)
        if not tickers:
            logger.warning("IngestFundamentals: nenhum ticker para processar")
            ctx["ingest_fundamentals_count"] = 0
            return ctx

        logger.info(f"IngestFundamentals: {len(tickers)} tickers a processar")

        fetcher = YahooFinanceFetcher()
        total_count = 0
        today = date.today()
        period = f"{today.year}-Q{(today.month - 1) // 3 + 1}"

        for ticker in tickers:
            try:
                # Busca info básica (contém indicadores fundamentalistas)
                info = fetcher.get_basic_info(ticker)
                if not info:
                    continue

                # Extrai indicadores disponíveis
                indicators = {}
                for key in self.YAHOO_INDICATORS:
                    val = info.get(key)
                    if val is not None:
                        try:
                            indicators[key] = float(val)
                        except (ValueError, TypeError):
                            pass

                if indicators:
                    stored = lake.store_fundamentals(
                        ticker, period, indicators, "yahoo"
                    )
                    total_count += stored
                    logger.debug(f"  {ticker}: {stored} indicadores")

                # Busca financials (DRE, Balanço, DFC)
                financials = fetcher.get_financials(ticker)
                if financials:
                    for stmt_type, stmt_data in financials.items():
                        if hasattr(stmt_data, "to_dict"):
                            lake.store_statement(
                                ticker,
                                period,
                                stmt_type,
                                stmt_data.to_dict(),
                                "yahoo",
                            )

            except Exception as e:
                logger.warning(f"Erro ao processar fundamentos de {ticker}: {e}")

        ctx["ingest_fundamentals_count"] = total_count
        logger.info(f"IngestFundamentals: {total_count} registros persistidos no lake")
        return ctx

    def _collect_tickers(self, ctx: PipelineContext) -> list[str]:
        """Coleta tickers de ações e FIIs da carteira."""
        if self._tickers:
            return self._tickers

        portfolio = ctx.get("portfolio")
        if not portfolio:
            return []

        # Filtra apenas ações e FIIs (fundamentals não fazem sentido para RF/ETFs internacionais)
        equity_classes = {"Ações", "Fundos de Investimentos"}
        return [a.ticker for a in portfolio.assets if a.classe in equity_classes]


class IngestNewsNode(Node):
    """Busca notícias financeiras e persiste no DataLake.

    Busca headlines de fontes de notícias (NewsAPI, RSS) e persiste no
    NewsLake com metadados de categoria, tickers mencionados e fonte.

    Quando NewsApiFetcher e RSSFetcher estiverem disponíveis (Fase 5),
    serão as fontes primárias. Por enquanto, este node serve como
    esqueleto para a ingestão futura.

    Produz no contexto:
        - "ingest_news_count": int (artigos persistidos)
        - "data_lake": DataLake
    """

    name = "ingest_news"
    dependencies: list[str] = []

    def __init__(self, sources: list[str] | None = None):
        self._sources = sources or ["newsapi"]

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.lake import DataLake

        lake = ctx.get("data_lake") or DataLake(settings.paths.LAKE_DIR)
        ctx["data_lake"] = lake

        total_count = 0

        for source in self._sources:
            try:
                articles = self._fetch_from_source(source)
                if articles:
                    count = lake.store_news(articles, source=source)
                    total_count += count
                    logger.debug(f"  {source}: {count} artigos")
            except Exception as e:
                logger.warning(f"Erro ao buscar notícias de {source}: {e}")

        ctx["ingest_news_count"] = total_count
        logger.info(f"IngestNews: {total_count} artigos persistidos no lake")
        return ctx

    def _fetch_from_source(self, source: str) -> list[dict]:
        """Busca artigos de uma fonte específica.

        Retorna lista de dicts com campos compatíveis com NewsLake.store().
        Fetchers específicos serão implementados na Fase 5.
        """
        if source == "newsapi":
            return self._fetch_newsapi()
        elif source == "rss":
            return self._fetch_rss()
        else:
            logger.warning(f"Fonte de notícias '{source}' não implementada")
            return []

    def _fetch_newsapi(self) -> list[dict]:
        """Busca notícias via NewsAPI (quando disponível)."""
        api_key = settings.API_KEYS.get("newsapi")
        if not api_key:
            logger.debug("NewsAPI key não configurada, pulando ingestão")
            return []

        # NewsApiFetcher será implementado na Fase 5
        logger.debug("NewsApiFetcher ainda não implementado (Fase 5)")
        return []

    def _fetch_rss(self) -> list[dict]:
        """Busca notícias via RSS feeds (quando disponível)."""
        # RSSFetcher será implementado na Fase 5
        logger.debug("RSSFetcher ainda não implementado (Fase 5)")
        return []
