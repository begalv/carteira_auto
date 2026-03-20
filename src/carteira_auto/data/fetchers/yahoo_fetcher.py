"""Fetcher otimizado para dados do Yahoo Finance com suporte completo à API."""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Union

import pandas as pd
import yfinance as yf
from yfinance import Calendars, Market, Search, Ticker, download

from carteira_auto.config import constants, settings
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_by_ticker,
    cache_result,
    log_execution,
    rate_limit,
    retry,
    timeout,
    validate_tickers,
)
from carteira_auto.utils.helpers import validate_ticker

logger = get_logger(__name__)


class YahooFinanceFetcher:
    """Classe otimizada para buscar dados do Yahoo Finance com suporte completo à API."""

    def __init__(self, max_workers: Optional[int] = None):
        """Inicializa o fetcher com configurações otimizadas.

        Args:
            max_workers: Número máximo de threads para operações paralelas.
                        Se None, usa min(32, os.cpu_count() + 4) como padrão otimizado.
        """

        # Configurações de performance
        self.max_workers = max_workers or min(32, os.cpu_count() + 4)
        self.timeout = settings.fetcher.YAHOO_TIMEOUT
        self.retries = settings.fetcher.YAHOO_RETRIES
        self.rate_limit_calls = settings.fetcher.RATE_LIMIT_REQUESTS

        # Configura o yfinance
        self._configure_yfinance()

        logger.info(
            f"YahooFinanceFetcher inicializado: workers={self.max_workers}, "
            f"timeout={self.timeout}s, retries={self.retries}"
        )

    def _configure_yfinance(self) -> None:
        """Configura opções globais do yfinance."""
        try:
            if settings.DEBUG:
                yf.enable_debug_mode()
                logger.info("Modo debug do yfinance ativado")
        except Exception as e:
            logger.warning(f"Erro ao configurar yfinance: {e}")

    # ============================================================================
    # DADOS HISTÓRICOS
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS * 2)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT * 2)
    @validate_tickers
    @log_execution
    @cache_result(ttl_seconds=86400)  # 24h
    def get_historical_price_data(
        self,
        symbols: Union[str, list[str]],
        period: str = "10y",
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Obtém dados históricos de preço de um ou mais ativos.

        Para preços atuais, use period="1d".
        """
        try:
            data = download(
                tickers=symbols,
                period=period,
                interval=interval,
                start=start,
                end=end,
                repair=True,
                threads=True,
                progress=settings.DEBUG,
                group_by="ticker",
                **kwargs,
            )

            if data.empty:
                logger.warning(f"Nenhum dado histórico encontrado para {symbols}")
                return pd.DataFrame()

            logger.info(
                f"Dados históricos obtidos para {symbols}: {len(data)} registros"
            )
            return data

        except Exception as e:
            logger.error(f"Erro ao buscar dados históricos: {e}", exc_info=True)
            return pd.DataFrame()

    # ============================================================================
    # INFORMAÇÕES COMPLETAS DO TICKER
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT * 2)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_ticker_info(self, symbol: str) -> Optional[dict[str, Any]]:
        """Obtém informações completas de um ticker (todas as disponíveis)."""
        try:
            ticker = Ticker(symbol)

            # Coleta TODAS as informações disponíveis
            result = {
                # Informações básicas
                "info": ticker.info,
                # Dados de mercado
                "history": ticker.history(period="1mo"),
                "dividends": ticker.dividends,
                "splits": ticker.splits,
                "capital_gains": ticker.capital_gains,
                "actions": ticker.actions,
                # Dados financeiros
                "financials": ticker.financials,
                "quarterly_financials": ticker.quarterly_financials,
                "balance_sheet": ticker.balance_sheet,
                "quarterly_balance_sheet": ticker.quarterly_balance_sheet,
                "cashflow": ticker.cashflow,
                "quarterly_cashflow": ticker.quarterly_cashflow,
                # Earnings
                "earnings": ticker.earnings,
                "quarterly_earnings": ticker.quarterly_earnings,
                # Análise
                "recommendations": ticker.recommendations,
                "recommendations_summary": ticker.recommendations_summary,
                "upgrades_downgrades": ticker.upgrades_downgrades,
                "earnings_dates": ticker.earnings_dates,
                "earnings_history": ticker.earnings_history,
                # Holders
                "major_holders": ticker.major_holders,
                "institutional_holders": ticker.institutional_holders,
                "mutualfund_holders": ticker.mutualfund_holders,
                "insider_transactions": ticker.insider_transactions,
                "insider_purchases": ticker.insider_purchases,
                "insider_roster_holders": ticker.insider_roster_holders,
                # Informações adicionais
                "calendar": ticker.calendar,
                "isin": ticker.isin,
                "options": ticker.options,
                "news": ticker.news,
                "shares": ticker.shares,
                "analyst_price_target": ticker.analyst_price_target,
                "growth_estimates": ticker.growth_estimates,
            }

            # Remove entradas vazias/nulas
            result = {
                k: v
                for k, v in result.items()
                if v is not None and (not hasattr(v, "empty") or not v.empty)
            }

            logger.info(f"Informações obtidas para {symbol}: {len(result)} categorias")
            return result

        except Exception as e:
            logger.error(f"Erro ao obter informações para {symbol}: {e}", exc_info=True)
            return None

    # ============================================================================
    # DIVIDENDOS E YIELD
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_dividend_yield(self, symbol: str) -> Optional[float]:
        """Obtém o dividend yield de um ativo."""
        try:
            ticker = Ticker(symbol)
            info = ticker.info

            # Tenta múltiplos campos
            dy_fields = [
                "dividendYield",
                "trailingAnnualDividendYield",
                "forwardDividendYield",
                "yield",
            ]

            for field in dy_fields:
                dy = info.get(field)
                if dy is not None:
                    dy_value = float(dy)
                    logger.info(f"Dividend yield de {symbol}: {dy_value:.2%}")
                    return dy_value

            # Calcula a partir de dividendos
            dividends = ticker.dividends
            if not dividends.empty:
                current_price = self.get_current_price(symbol)
                if current_price and current_price > 0:
                    annual_dividend = dividends.tail(4).sum()
                    dy_value = annual_dividend / current_price
                    logger.info(
                        f"Dividend yield calculado para {symbol}: {dy_value:.2%}"
                    )
                    return float(dy_value)

            logger.warning(f"Nenhum dividend yield encontrado para {symbol}")
            return None

        except Exception as e:
            logger.error(f"Erro ao obter dividend yield para {symbol}: {e}")
            return None

    # ============================================================================
    # MERCADO E PESQUISA
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=300)  # 5min
    def get_market_summary(self, market: str = "us") -> Optional[dict[str, Any]]:
        """Obtém resumo do mercado.

        Args:
            market: Código do mercado ('us', 'br', 'au', etc.)
                   Padrão: 'us' (mercado americano)
        """
        try:
            market_obj = Market(market)
            summary = market_obj.summary

            if not summary:
                logger.warning(f"Nenhum resumo de mercado encontrado para {market}")
                return None

            logger.info(
                f"Resumo do mercado {market} obtido: {len(summary)} indicadores"
            )
            return summary

        except Exception as e:
            logger.error(f"Erro ao obter resumo do mercado {market}: {e}")
            return None

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def search_tickers(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Busca tickers."""
        try:
            search = Search(query)
            results = search.results

            if not results:
                logger.warning(f"Nenhum resultado encontrado para: {query}")
                return []

            limited_results = results[:limit]
            logger.debug(f"{len(limited_results)} resultados encontrados para: {query}")

            return limited_results

        except Exception as e:
            logger.error(f"Erro na busca por '{query}': {e}")
            return []

    # ============================================================================
    # CALENDÁRIO
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def get_market_calendar(self, days: int = 30) -> Optional[pd.DataFrame]:
        """Obtém calendário de eventos do mercado.

        Args:
            days: Número de dias para frente (padrão: 30)
        """
        try:
            calendars = Calendars(days=days)
            calendar_data = calendars.events

            if calendar_data.empty:
                logger.warning("Nenhum evento de calendário encontrado")
                return None

            logger.debug(f"Calendário obtido: {len(calendar_data)} eventos")
            return calendar_data

        except Exception as e:
            logger.error(f"Erro ao obter calendário: {e}")
            return None

    # ============================================================================
    # OPÇÕES
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @validate_tickers
    def get_options_chain(
        self, symbol: str, expiration: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Obtém a cadeia de opções."""
        try:
            ticker = Ticker(symbol)
            options_dates = ticker.options

            if not options_dates:
                logger.warning(f"Nenhuma opção disponível para {symbol}")
                return None

            # Usa data fornecida ou a mais próxima
            target_date = (
                expiration
                if expiration and expiration in options_dates
                else options_dates[0]
            )

            options = ticker.option_chain(target_date)

            result = {
                "calls": options.calls,
                "puts": options.puts,
                "expiration": target_date,
                "available_dates": options_dates,
                "underlying_price": self.get_current_price(symbol),
            }

            logger.debug(f"Cadeia de opções obtida para {symbol}")
            return result

        except Exception as e:
            logger.error(f"Erro ao obter opções para {symbol}: {e}")
            return None

    # ============================================================================
    # PREÇO INDIVIDUAL E MÚLTIPLO
    # ============================================================================

    @staticmethod
    def normalize_br_ticker(ticker: str) -> str:
        """Adiciona sufixo .SA para tickers B3 se necessário.

        Ignora tickers que já possuem sufixo, tickers de Tesouro Direto
        e tickers que não seguem padrões B3.
        """
        if ticker in constants.NON_YAHOO_TICKERS:
            return ticker
        if "." in ticker or "-" in ticker:
            return ticker
        # Padrões B3 definidos em constants
        for pattern in constants.VALID_TICKER_PATTERNS.values():
            if re.match(pattern, ticker):
                return f"{ticker}.SA"
        # Padrão genérico B3: letras/dígitos terminando em 2 dígitos
        # Cobre ETFs como B5P211, BOVA11, HASH11, Units como SAPR11
        if re.match(r"^[A-Z0-9]{4,6}\d{2}$", ticker):
            return f"{ticker}.SA"
        # BDRs com sufixo 34/39 e nomes maiores (ex: BSLV39, M1TA34)
        if re.match(r"^[A-Z0-9]{4,6}(34|39)$", ticker):
            return f"{ticker}.SA"
        return ticker

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_by_ticker(ttl_seconds=300)  # 5min
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Obtém o preço mais recente de um ativo."""
        try:
            ticker = Ticker(symbol)
            info = ticker.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price is not None:
                return float(price)

            hist = ticker.history(period="5d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])

            logger.warning(f"Nenhum preço encontrado para {symbol}")
            return None

        except Exception as e:
            logger.error(f"Erro ao obter preço de {symbol}: {e}")
            return None

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT * 2)
    @log_execution
    def get_multiple_prices(self, symbols: list[str]) -> dict[str, Optional[float]]:
        """Obtém preços atuais de múltiplos ativos via yf.download.

        Aceita tickers originais (ex: PETR4) — a normalização para o
        formato Yahoo (ex: PETR4.SA) e a filtragem de tickers incompatíveis
        (ex: Tesouro Direto) são feitas internamente.
        Os resultados são retornados com as chaves originais.
        """
        if not symbols:
            return {}

        # Filtra tickers que o Yahoo não resolve (Tesouro Direto etc.)
        eligible = [s for s in symbols if s not in constants.NON_YAHOO_TICKERS]
        skipped = {s: None for s in symbols if s in constants.NON_YAHOO_TICKERS}

        if not eligible:
            logger.warning("Nenhum ticker elegível para o Yahoo Finance")
            return skipped

        # Normaliza tickers e mantém mapeamento reverso
        original_to_yahoo = {s: self.normalize_br_ticker(s) for s in eligible}
        yahoo_to_original = {v: k for k, v in original_to_yahoo.items()}
        yahoo_symbols = list(original_to_yahoo.values())

        results: dict[str, Optional[float]] = {}
        try:
            data = download(
                tickers=yahoo_symbols,
                period="5d",
                interval="1d",
                threads=True,
                progress=False,
            )

            if data.empty:
                logger.warning(f"Nenhum dado retornado para {symbols}")
                return {s: None for s in symbols}

            if len(yahoo_symbols) == 1:
                # yf.download retorna colunas simples para ticker único
                if "Close" in data.columns:
                    last_close = data["Close"].dropna().iloc[-1]
                    results[symbols[0]] = float(last_close)
                else:
                    results[symbols[0]] = None
            else:
                for yahoo_sym in yahoo_symbols:
                    original = yahoo_to_original[yahoo_sym]
                    try:
                        close = data["Close"][yahoo_sym].dropna()
                        results[original] = (
                            float(close.iloc[-1]) if not close.empty else None
                        )
                    except (KeyError, IndexError):
                        results[original] = None

        except Exception as e:
            logger.error(f"Erro ao obter preços múltiplos: {e}")
            return {s: None for s in symbols}

        # Preenche tickers faltantes
        for s in eligible:
            if s not in results:
                results[s] = None

        # Inclui tickers que foram ignorados
        results.update(skipped)

        logger.info(
            f"Preços obtidos: {sum(1 for v in results.values() if v is not None)}"
            f"/{len(symbols)} tickers"
        )
        return results

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT * 2)
    @log_execution
    @cache_result(ttl_seconds=86400)  # 24h
    def get_historical_data(self, symbol: str, period: str = "1mo") -> pd.DataFrame:
        """Obtém dados históricos de um ativo (wrapper simplificado)."""
        try:
            ticker = Ticker(symbol)
            data = ticker.history(period=period)
            if data.empty:
                logger.warning(f"Nenhum dado histórico para {symbol}")
            return data
        except Exception as e:
            logger.error(f"Erro ao obter histórico de {symbol}: {e}")
            return pd.DataFrame()

    # ============================================================================
    # BATCH OPERATIONS OTIMIZADAS
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS * 2)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT * 2)
    @log_execution
    def get_batch_data(
        self, symbols: list[str], data_types: list[str] = None
    ) -> dict[str, dict[str, Any]]:
        """Obtém múltiplos tipos de dados para múltiplos símbolos (otimizado)."""
        if data_types is None:
            data_types = ["price", "info", "dividend_yield"]

        if not symbols:
            logger.warning("Lista de símbolos vazia")
            return {}

        results = {s: {} for s in symbols}

        # Para preços, usa download em lote (mais eficiente)
        if "price" in data_types:
            prices = self.get_multiple_prices(symbols)
            for symbol in symbols:
                results[symbol]["price"] = prices.get(symbol)

        # Para outros tipos, usa threading com paralelismo real
        other_types = [dt for dt in data_types if dt != "price"]
        if other_types:
            fetcher_map = {
                "info": self.get_ticker_info,
                "dividend_yield": self.get_dividend_yield,
                "historical": lambda s: self.get_historical_data(s, period="1mo"),
            }

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submete todas as tarefas de uma vez
                futures = {}
                for symbol in symbols:
                    for data_type in other_types:
                        fetcher_fn = fetcher_map.get(data_type)
                        if fetcher_fn:
                            future = executor.submit(fetcher_fn, symbol)
                            futures[future] = (symbol, data_type)

                # Coleta resultados conforme ficam prontos
                from concurrent.futures import as_completed

                for future in as_completed(futures, timeout=self.timeout):
                    symbol, data_type = futures[future]
                    try:
                        results[symbol][data_type] = future.result()
                    except Exception as e:
                        logger.error(f"Erro ao obter {data_type} para {symbol}: {e}")
                        results[symbol][data_type] = None

        logger.info(f"Batch data concluído para {len(symbols)} símbolos")
        return results

    # ============================================================================
    # VALIDAÇÃO
    # ============================================================================

    @log_execution
    def validate_symbol(self, symbol: str) -> tuple[bool, str]:
        """Valida se um símbolo existe no Yahoo Finance."""
        try:
            # Valida formato
            is_valid, ticker_type = validate_ticker(symbol)
            if not is_valid:
                return False, f"Formato inválido: {ticker_type}"

            # Verifica existência
            ticker = Ticker(symbol)
            info = ticker.info

            if not info or "symbol" not in info:
                return False, "Não encontrado no Yahoo Finance"

            return True, ticker_type

        except Exception as e:
            return False, f"Erro de validação: {str(e)}"

    # ============================================================================
    # SETORES E INDÚSTRIAS
    # ============================================================================

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def get_sector_performance(
        self, sector: str = "communication_services"
    ) -> Optional[dict[str, Any]]:
        """Obtém performance de um setor específico.

        Args:
            sector: Nome do setor. Opções comuns:
                   'communication_services', 'consumer_cyclical', 'consumer_defensive',
                   'energy', 'financial_services', 'healthcare', 'industrials',
                   'real_estate', 'technology', 'utilities'

        Returns:
            Dicionário com informações do setor ou None se não disponível.

        Nota:
            Esta funcionalidade pode não estar disponível em todas as versões do yfinance
            ou para todos os setores.
        """
        try:
            sector_obj = yf.Sector(sector)

            # Verifica se tem informações disponíveis
            if hasattr(sector_obj, "info") and sector_obj.info:
                logger.debug(f"Performance do setor {sector} obtida")
                return sector_obj.info
            else:
                logger.warning(f"Nenhuma informação disponível para o setor {sector}")
                return None

        except Exception as e:
            logger.debug(f"Performance do setor {sector} não disponível: {e}")
            return None

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def get_industry_performance(
        self, industry: str = "entertainment"
    ) -> Optional[dict[str, Any]]:
        """Obtém performance de uma indústria específica.

        Args:
            industry: Nome da indústria. Exemplos:
                     'entertainment', 'software', 'banks', 'insurance',
                     'pharmaceuticals', 'oil_gas', 'retail'

        Returns:
            Dicionário com informações da indústria ou None se não disponível.

        Nota:
            Esta funcionalidade pode não estar disponível em todas as versões do yfinance
            ou para todas as indústrias.
        """
        try:
            industry_obj = yf.Industry(industry)

            # Verifica se tem informações disponíveis
            if hasattr(industry_obj, "info") and industry_obj.info:
                logger.debug(f"Performance da indústria {industry} obtida")
                return industry_obj.info
            else:
                logger.warning(
                    f"Nenhuma informação disponível para a indústria {industry}"
                )
                return None

        except Exception as e:
            logger.debug(f"Performance da indústria {industry} não disponível: {e}")
            return None

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def list_available_sectors(self) -> list[str]:
        """Lista setores disponíveis para consulta.

        Returns:
            Lista de setores disponíveis ou lista vazia se não for possível obter.
        """
        try:
            # Setores comuns no Yahoo Finance
            common_sectors = [
                "communication_services",
                "consumer_cyclical",
                "consumer_defensive",
                "energy",
                "financial_services",
                "healthcare",
                "industrials",
                "real_estate",
                "technology",
                "utilities",
                "basic_materials",
            ]

            # Filtra setores que realmente existem
            available_sectors = []
            for sector in common_sectors:
                try:
                    sector_obj = yf.Sector(sector)
                    if hasattr(sector_obj, "info") and sector_obj.info:
                        available_sectors.append(sector)
                except Exception:
                    continue

            logger.debug(f"Setores disponíveis: {len(available_sectors)}")
            return available_sectors

        except Exception as e:
            logger.debug(f"Erro ao listar setores: {e}")
            return []

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def list_available_industries(self) -> list[str]:
        """Lista indústrias disponíveis para consulta.

        Returns:
            Lista de indústrias disponíveis ou lista vazia se não for possível obter.
        """
        try:
            # Indústrias comuns no Yahoo Finance
            common_industries = [
                "entertainment",
                "software",
                "banks",
                "insurance",
                "pharmaceuticals",
                "oil_gas",
                "retail",
                "automotive",
                "aerospace",
                "telecom",
                "media",
                "biotechnology",
                "medical_devices",
                "real_estate_development",
                "construction",
                "agriculture",
                "mining",
                "transportation",
                "restaurants",
                "hotels",
            ]

            # Filtra indústrias que realmente existem
            available_industries = []
            for industry in common_industries:
                try:
                    industry_obj = yf.Industry(industry)
                    if hasattr(industry_obj, "info") and industry_obj.info:
                        available_industries.append(industry)
                except Exception:
                    continue

            logger.debug(f"Indústrias disponíveis: {len(available_industries)}")
            return available_industries

        except Exception as e:
            logger.debug(f"Erro ao listar indústrias: {e}")
            return []
