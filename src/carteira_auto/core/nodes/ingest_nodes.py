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

    # Universo de ações BR para screening de oportunidades (aprox. IBX100).
    # Inclui blue chips, small caps relevantes e FIIs de maior liquidez.
    # Usado além dos tickers da carteira para capturar todo o mercado B3.
    SCREENING_TICKERS_BR = [
        # --- Blue chips / Ibovespa ---
        "PETR4.SA",
        "VALE3.SA",
        "ITUB4.SA",
        "BBDC4.SA",
        "BBAS3.SA",
        "ABEV3.SA",
        "WEGE3.SA",
        "RENT3.SA",
        "SUZB3.SA",
        "JBSS3.SA",
        "RDOR3.SA",
        "RAIL3.SA",
        "EMBR3.SA",
        "BPAC11.SA",
        "EGIE3.SA",
        "CMIG4.SA",
        "ELET3.SA",
        "ELET6.SA",
        "CPLE6.SA",
        "ENGI11.SA",
        "EQTL3.SA",
        "TAEE11.SA",
        "SBSP3.SA",
        "SAPR11.SA",
        "TRPL4.SA",
        # --- Bancos e financeiras ---
        "SANB11.SA",
        "ITSA4.SA",
        "B3SA3.SA",
        "IRBR3.SA",
        "PSSA3.SA",
        "CXSE3.SA",
        "BBSE3.SA",
        "SULA11.SA",
        # --- Consumo e varejo ---
        "MGLU3.SA",
        "LREN3.SA",
        "AMER3.SA",
        "NTCO3.SA",
        "SOMA3.SA",
        "LWSA3.SA",
        "PETZ3.SA",
        "VIVA3.SA",
        "RECV3.SA",
        # --- Saúde ---
        "HAPV3.SA",
        "GNDI3.SA",
        "FLRY3.SA",
        "QUAL3.SA",
        "ONCO3.SA",
        "DASA3.SA",
        "HYPE3.SA",
        "PNVL3.SA",
        # --- Tecnologia e telecom ---
        "TIMS3.SA",
        "VIVT3.SA",
        "INTB3.SA",
        "TOTS3.SA",
        "POSI3.SA",
        "LWSA3.SA",
        # --- Petróleo, gás e mineração ---
        "PRIO3.SA",
        "RECV3.SA",
        "CMIN3.SA",
        "CSNA3.SA",
        "GGBR4.SA",
        "USIM5.SA",
        # --- Agro e papel/celulose ---
        "SLCE3.SA",
        "AGRO3.SA",
        "TTEN3.SA",
        "KLBN11.SA",
        "DXCO3.SA",
        # --- Imobiliário (CRI/CRA/FIIs) ---
        "CYRE3.SA",
        "MRVE3.SA",
        "EVEN3.SA",
        "DIRR3.SA",
        "TRISUL3.SA",
        "EZTC3.SA",
        # --- Transportes e logística ---
        "GOLL4.SA",
        "AZUL4.SA",
        "CCRO3.SA",
        "ECOR3.SA",
        "MOVI3.SA",
        "POMO4.SA",
        "ROMI3.SA",
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
        """Coleta tickers da carteira + benchmarks + commodities + crypto + screening BR."""
        tickers: set[str] = set()

        # Tickers da carteira (se disponível no contexto)
        portfolio = ctx.get("portfolio")
        if portfolio:
            for asset in portfolio.assets:
                tickers.add(asset.ticker)

        # Extras: referências globais
        tickers.update(self.BENCHMARK_TICKERS)
        tickers.update(self.COMMODITY_TICKERS)
        tickers.update(self.CRYPTO_TICKERS)
        tickers.update(self.FX_TICKERS)

        # Universo de screening BR para capturar oportunidades além da carteira
        tickers.update(self.SCREENING_TICKERS_BR)

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

        # --- DDM ---
        total_count += self._ingest_ddm_macro(lake)

        # --- FRED ---
        total_count += self._ingest_fred(lake)

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

    def _ingest_ddm_macro(self, lake) -> int:
        """Ingere indicadores macro do DDM (expectativas, índices econômicos).

        Cada indicador (SELIC, CDI, IPCA, etc.) é armazenado como uma série
        separada no MacroLake, usando o campo 'nome' ou 'indicador' da resposta
        DDM para nomear a série. Isso preserva a granularidade por indicador e
        permite consultas e gráficos independentes por série.
        """
        from carteira_auto.data.fetchers import DDMFetcher

        fetcher = DDMFetcher()
        count = 0

        # Índices econômicos — cada indicador vira uma série macro separada
        try:
            indices = fetcher.get_economic_indices()
            if indices:
                count += self._store_ddm_by_indicator(
                    lake,
                    records=indices,
                    prefix="ddm_indice",
                    name_fields=["nome", "indicador", "name"],
                    date_field="data",
                    value_field="valor",
                    unit_field="unidade",
                    default_unit="%",
                    frequency="daily",
                )
        except Exception as e:
            logger.warning(f"Erro ao buscar DDM/economic_indices: {e}")

        # Expectativas de mercado Focus — agrupadas por indicador e horizonte
        try:
            expectations = fetcher.get_market_expectations()
            if expectations:
                count += self._store_ddm_by_indicator(
                    lake,
                    records=expectations,
                    prefix="ddm_expectativa",
                    name_fields=["indicador", "nome", "name"],
                    date_field="data",
                    value_field="mediana",
                    default_unit="%",
                    frequency="weekly",
                )
        except Exception as e:
            logger.warning(f"Erro ao buscar DDM/market_expectations: {e}")

        return count

    def _store_ddm_by_indicator(
        self,
        lake,
        records: list[dict],
        prefix: str,
        name_fields: list[str],
        date_field: str,
        value_field: str,
        default_unit: str,
        frequency: str,
        unit_field: str | None = None,
    ) -> int:
        """Agrupa registros DDM por indicador e armazena cada um como série separada.

        Args:
            lake: Instância do DataLake.
            records: Lista de dicts retornada pelo DDMFetcher.
            prefix: Prefixo do nome da série (ex: "ddm_indice").
            name_fields: Campos candidatos para identificar o nome do indicador.
            date_field: Campo de data no dict DDM.
            value_field: Campo de valor numérico.
            default_unit: Unidade padrão se 'unit_field' não estiver presente.
            frequency: Frequência dos dados ("daily", "weekly", "monthly").
            unit_field: Campo opcional que contém a unidade do indicador.

        Returns:
            Número total de registros persistidos.
        """
        df_all = pd.DataFrame(records)
        if df_all.empty:
            return 0

        # Descobre qual campo usar como nome do indicador
        name_col = next((f for f in name_fields if f in df_all.columns), None)
        if not name_col:
            # Sem campo de nome — armazena tudo como série única com prefixo
            df = self._normalize_ddm_list(
                records, date_field=date_field, value_field=value_field
            )
            if df is None or df.empty:
                return 0
            stored = lake.store_macro(
                prefix, df, source="ddm", unit=default_unit, frequency=frequency
            )
            logger.debug(f"  DDM/{prefix}: {stored} registros (sem campo de nome)")
            return stored

        # Agrupa por indicador e armazena cada série separadamente
        total = 0
        for indicator_name, group in df_all.groupby(name_col):
            group_records = group.to_dict("records")
            df = self._normalize_ddm_list(
                group_records, date_field=date_field, value_field=value_field
            )
            if df is None or df.empty:
                continue

            # Nome da série: prefixo + indicador normalizado (ex: ddm_indice_selic)
            safe_name = (
                str(indicator_name)
                .lower()
                .replace(" ", "_")
                .replace("/", "_")
                .replace("-", "_")
            )
            series_name = f"{prefix}_{safe_name}"

            # Unidade: tenta pegar do próprio registro
            unit = default_unit
            if unit_field and unit_field in group.columns:
                unit = str(group[unit_field].iloc[0])

            stored = lake.store_macro(
                series_name, df, source="ddm", unit=unit, frequency=frequency
            )
            total += stored
            logger.debug(f"  DDM/{series_name}: {stored} registros")

        return total

    @staticmethod
    def _normalize_ddm_list(
        records: list[dict],
        date_field: str = "data",
        value_field: str = "valor",
    ) -> pd.DataFrame | None:
        """Normaliza lista de dicts DDM para DataFrame com date/value."""
        if not records:
            return None

        df = pd.DataFrame(records)

        if date_field not in df.columns or value_field not in df.columns:
            # Tenta campos alternativos comuns na API DDM
            alt_date = next(
                (c for c in df.columns if "data" in c.lower() or "date" in c.lower()),
                None,
            )
            alt_val = next(
                (
                    c
                    for c in df.columns
                    if "valor" in c.lower()
                    or "value" in c.lower()
                    or "mediana" in c.lower()
                ),
                None,
            )
            if not alt_date or not alt_val:
                return None
            date_field, value_field = alt_date, alt_val

        result = pd.DataFrame()
        result["date"] = pd.to_datetime(df[date_field], errors="coerce")
        result["value"] = pd.to_numeric(df[value_field], errors="coerce")
        return result.dropna(subset=["date", "value"]).reset_index(drop=True)

    def _ingest_fred(self, lake) -> int:
        """Ingere bundle macro do FRED (Fed Funds, Treasury 10Y, VIX, etc.)."""
        from carteira_auto.data.fetchers import FREDFetcher

        fetcher = FREDFetcher()
        if not fetcher._api_key:
            logger.debug("FRED API key não configurada, pulando ingestão FRED")
            return 0

        count = 0
        try:
            bundle = fetcher.get_macro_bundle()
            for series_id, df in bundle.items():
                if df is None or df.empty:
                    continue
                # FRED DataFrame já tem date/value — apenas remove series_id
                df_clean = df[["date", "value"]].copy()
                meta = fetcher.list_series().get(series_id, {})
                stored = lake.store_macro(
                    f"fred_{series_id.lower()}",
                    df_clean,
                    source="fred",
                    unit=meta.get("unidade", ""),
                    frequency=meta.get("frequencia", "daily"),
                )
                count += stored
                logger.debug(f"  FRED/{series_id}: {stored} registros")
        except Exception as e:
            logger.warning(f"Erro ao buscar bundle FRED: {e}")

        return count


class IngestFundamentalsNode(Node):
    """Busca dados fundamentalistas e persiste no DataLake.

    Busca indicadores fundamentalistas (P/L, P/VP, ROE, DY, etc.) e
    demonstrações financeiras via YahooFinanceFetcher em paralelo
    (ThreadPoolExecutor via get_batch_info) e persiste no FundamentalsLake.

    Cobre dois universos de tickers:
    - Carteira: tickers de ações e FIIs do portfólio atual.
    - Screening: universo BR (~60 ações) para identificar oportunidades
      além da carteira, usando IngestPricesNode.SCREENING_TICKERS_BR.

    DDM complementa com série histórica de DRE, balanço e DFC por ticker.

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
        """Executa a ingestão de fundamentos no DataLake.

        Usa get_batch_info() com ThreadPoolExecutor para buscar info e
        financials de todos os tickers em paralelo, evitando a latência
        de chamadas sequenciais por ticker.
        """
        from carteira_auto.data.fetchers import YahooFinanceFetcher
        from carteira_auto.data.lake import DataLake

        lake = ctx.get("data_lake") or DataLake(settings.paths.LAKE_DIR)
        ctx["data_lake"] = lake

        tickers = self._collect_tickers(ctx)
        if not tickers:
            logger.warning("IngestFundamentals: nenhum ticker para processar")
            ctx["ingest_fundamentals_count"] = 0
            return ctx

        logger.info(
            f"IngestFundamentals: {len(tickers)} tickers a processar (paralelo)"
        )

        fetcher = YahooFinanceFetcher()
        total_count = 0
        today = date.today()
        period = f"{today.year}-Q{(today.month - 1) // 3 + 1}"

        # Busca info + financials em paralelo via ThreadPoolExecutor interno do Yahoo
        batch_result = fetcher.get_batch_info(tickers, fields=["info", "financials"])

        for ticker, data in batch_result.items():
            try:
                # --- Info: indicadores fundamentalistas ---
                info = data.get("info") or {}
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

                # --- Financials: DRE, Balanço, DFC ---
                financials = data.get("financials") or {}
                for stmt_type, stmt_data in financials.items():
                    if hasattr(stmt_data, "to_dict"):
                        lake.store_statement(
                            ticker, period, stmt_type, stmt_data.to_dict(), "yahoo"
                        )

            except Exception as e:
                logger.warning(f"Erro ao processar fundamentos de {ticker}: {e}")

        # DDM como fonte complementar (série histórica de DRE, balanço, DFC)
        total_count += self._ingest_ddm_fundamentals(lake, tickers, period)

        ctx["ingest_fundamentals_count"] = total_count
        logger.info(f"IngestFundamentals: {total_count} registros persistidos no lake")
        return ctx

    def _collect_tickers(self, ctx: PipelineContext) -> list[str]:
        """Coleta tickers de ações/FIIs da carteira + universo de screening BR.

        Sempre inclui IngestPricesNode.SCREENING_TICKERS_BR para garantir
        cobertura de oportunidades além da carteira atual.
        Se tickers explícitos foram passados no construtor, usa apenas eles.
        """
        if self._tickers is not None:
            return self._tickers

        tickers: set[str] = set()

        # Tickers de ações e FIIs da carteira (fundamentals não fazem sentido para RF/ETFs internacionais)
        portfolio = ctx.get("portfolio")
        if portfolio:
            equity_classes = {"Ações", "Fundos de Investimentos"}
            tickers.update(
                a.ticker for a in portfolio.assets if a.classe in equity_classes
            )

        # Universo de screening BR para identificar oportunidades além da carteira
        tickers.update(IngestPricesNode.SCREENING_TICKERS_BR)

        return sorted(tickers)

    def _ingest_ddm_fundamentals(self, lake, tickers: list[str], period: str) -> int:
        """Ingere série histórica de fundamentos via DDM (DRE, balanço, DFC, ações).

        DDM retorna dados históricos por período, complementando o snapshot do Yahoo.
        Armazena como statements no FundamentalsLake.
        """
        from carteira_auto.data.fetchers import DDMFetcher

        fetcher = DDMFetcher()
        if not fetcher._api_key:
            logger.debug(
                "DDM API key não configurada, pulando ingestão DDM fundamentals"
            )
            return 0

        count = 0

        # Mapeamento: nome do statement → método DDM
        ddm_statements = {
            "income_statement_ddm": "get_income_statement",
            "cash_flow_ddm": "get_cash_flow",
            "balance_sheet_ddm": "get_balance_sheet",
        }

        for ticker in tickers:
            # Remove sufixo .SA se presente (DDM usa ticker sem sufixo)
            clean_ticker = ticker.replace(".SA", "").upper()
            for stmt_name, method_name in ddm_statements.items():
                try:
                    method = getattr(fetcher, method_name)
                    data = method(clean_ticker)
                    if data:
                        lake.store_statement(ticker, period, stmt_name, data, "ddm")
                        count += len(data) if isinstance(data, list) else 1
                        logger.debug(
                            f"  DDM/{ticker}/{stmt_name}: {len(data) if isinstance(data, list) else 1} itens"
                        )
                except Exception as e:
                    logger.debug(f"DDM fundamentos {ticker}/{stmt_name}: {e}")

        return count


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

    def __init__(
        self, sources: list[str] | None = None, tickers: list[str] | None = None
    ):
        self._sources = sources or ["ddm", "newsapi"]
        self._tickers = tickers  # Tickers opcionais para filtrar notícias

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
        """
        if source == "ddm":
            return self._fetch_ddm()
        elif source == "newsapi":
            return self._fetch_newsapi()
        elif source == "rss":
            return self._fetch_rss()
        else:
            logger.warning(f"Fonte de notícias '{source}' não implementada")
            return []

    def _fetch_ddm(self) -> list[dict]:
        """Busca notícias via DDM (Dados de Mercado)."""
        from carteira_auto.data.fetchers import DDMFetcher

        fetcher = DDMFetcher()
        if not fetcher._api_key:
            logger.debug("DDM API key não configurada, pulando ingestão DDM news")
            return []

        articles = []
        tickers_to_fetch = self._tickers or [None]  # None = notícias gerais

        for ticker in tickers_to_fetch:
            try:
                raw = fetcher.get_news(ticker=ticker)
                if raw:
                    normalized = [self._normalize_ddm_article(a, ticker) for a in raw]
                    articles.extend(normalized)
            except Exception as e:
                logger.debug(f"DDM news {ticker}: {e}")

        return articles

    @staticmethod
    def _normalize_ddm_article(article: dict, ticker: str | None) -> dict:
        """Normaliza artigo DDM para o formato do NewsLake."""
        return {
            "title": article.get("titulo") or article.get("title", ""),
            "summary": article.get("resumo") or article.get("summary", ""),
            "url": article.get("url", ""),
            "published_at": article.get("data_publicacao")
            or article.get("published_at", ""),
            "source": article.get("fonte") or article.get("source", "ddm"),
            "category": "mercado",
            "tickers": [ticker] if ticker else [],
        }

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


class IngestCVMNode(Node):
    """Busca demonstrações financeiras da CVM e persiste no DataLake.

    Busca DFP (anual) e ITR (trimestral) da CVM para as empresas
    da carteira e persiste como statements no FundamentalsLake.

    Lê do contexto (opcional):
        - "portfolio": Portfolio (usa tickers de ações)

    Produz no contexto:
        - "ingest_cvm_count": int (registros persistidos)
        - "data_lake": DataLake
    """

    name = "ingest_cvm"
    dependencies: list[str] = []

    def __init__(
        self,
        tickers: list[str] | None = None,
        year: int | None = None,
        statements: list[str] | None = None,
    ):
        self._tickers = tickers
        self._year = year or date.today().year - 1  # Ano anterior (DFP já disponível)
        self._statements = statements or ["DRE", "BPA", "BPP", "DFC_MD"]

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.fetchers import CVMFetcher
        from carteira_auto.data.lake import DataLake

        lake = ctx.get("data_lake") or DataLake(settings.paths.LAKE_DIR)
        ctx["data_lake"] = lake

        tickers = self._collect_tickers(ctx)
        if not tickers:
            logger.warning("IngestCVM: nenhum ticker de ações para processar")
            ctx["ingest_cvm_count"] = 0
            return ctx

        logger.info(f"IngestCVM: {len(tickers)} tickers, ano {self._year}")

        fetcher = CVMFetcher()
        total_count = 0
        period = str(self._year)

        for ticker in tickers:
            cnpj = fetcher.get_cnpj_by_ticker(ticker)
            if not cnpj:
                logger.debug(f"IngestCVM: CNPJ não encontrado para {ticker}")
                continue

            for stmt in self._statements:
                try:
                    df = fetcher.get_dfp(cnpj, self._year, stmt)
                    if df is not None and not df.empty:
                        lake.store_statement(
                            ticker,
                            period,
                            f"cvm_{stmt.lower()}",
                            df.to_dict("records"),
                            "cvm",
                        )
                        total_count += len(df)
                        logger.debug(f"  CVM/{ticker}/{stmt}: {len(df)} linhas")
                except Exception as e:
                    logger.debug(f"CVM {ticker}/{stmt}: {e}")

        ctx["ingest_cvm_count"] = total_count
        logger.info(f"IngestCVM: {total_count} registros persistidos no lake")
        return ctx

    def _collect_tickers(self, ctx: PipelineContext) -> list[str]:
        """Coleta tickers de ações (apenas empresas listadas têm dados na CVM)."""
        if self._tickers is not None:
            return self._tickers

        portfolio = ctx.get("portfolio")
        if not portfolio:
            return []

        return [a.ticker for a in portfolio.assets if a.classe == "Ações"]


class IngestTesouroDiretoNode(Node):
    """Busca dados históricos do Tesouro Direto e persiste no DataLake.

    Busca preços e taxas históricos de LFT, NTN-B, LTN e NTN-F
    e persiste no MacroLake para análise de renda fixa.

    Produz no contexto:
        - "ingest_tesouro_count": int (registros persistidos)
        - "data_lake": DataLake
    """

    name = "ingest_tesouro"
    dependencies: list[str] = []

    # Tipos de título a ingerir por default
    DEFAULT_TIPOS = ["LFT", "NTN-B", "LTN", "NTN-F"]

    def __init__(self, tipos: list[str] | None = None):
        self._tipos = tipos or self.DEFAULT_TIPOS

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        from carteira_auto.data.fetchers import TesouroDiretoFetcher
        from carteira_auto.data.lake import DataLake

        lake = ctx.get("data_lake") or DataLake(settings.paths.LAKE_DIR)
        ctx["data_lake"] = lake

        fetcher = TesouroDiretoFetcher()
        total_count = 0

        for tipo in self._tipos:
            try:
                df = fetcher.get_price_history_by_type(tipo)
                if df is None or df.empty:
                    continue

                # Converte cada vencimento como série macro independente
                if (
                    "vencimento" in df.columns
                    and "data" in df.columns
                    and "taxa_compra" in df.columns
                ):
                    for vencimento in df["vencimento"].dropna().unique():
                        df_venc = df[df["vencimento"] == vencimento][
                            ["data", "taxa_compra"]
                        ].copy()
                        df_venc = df_venc.rename(
                            columns={"data": "date", "taxa_compra": "value"}
                        )
                        df_venc = df_venc.dropna(subset=["value"])

                        if df_venc.empty:
                            continue

                        venc_str = (
                            pd.Timestamp(vencimento).strftime("%Y-%m")
                            if pd.notna(vencimento)
                            else "unknown"
                        )
                        indicator_name = (
                            f"tesouro_{tipo.lower().replace('-', '_')}_{venc_str}"
                        )

                        stored = lake.store_macro(
                            indicator_name,
                            df_venc,
                            source="tesouro_direto",
                            unit="% a.a.",
                            frequency="daily",
                        )
                        total_count += stored

                logger.debug(f"  Tesouro/{tipo}: processado")

            except Exception as e:
                logger.warning(f"Erro ao ingerir Tesouro/{tipo}: {e}")

        ctx["ingest_tesouro_count"] = total_count
        logger.info(f"IngestTesouroDireto: {total_count} registros persistidos no lake")
        return ctx
