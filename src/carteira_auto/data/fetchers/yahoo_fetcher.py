"""Fetcher otimizado para dados do Yahoo Finance com suporte completo à API."""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Union

import pandas as pd
import yfinance as yf
from yfinance import Calendars, Market, Search, Ticker, download

from carteira_auto.config import settings
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
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_result(ttl_seconds=300)  # 5min
    def get_current_price_data(
        self, symbols: Union[str, list[str]], **kwargs
    ) -> pd.DataFrame:
        """Obtém os dados de preço de um ou mais ativos na data mais recente disponível."""

        if settings.DEBUG:
            progress = True
        else:
            progress = False

        # Buscar dados de apenas 1 dia é mais rápido e eficiente para atualizar preços atuais
        try:
            data = download(
                tickers=symbols,
                period="1d",
                interval="1d",
                repair=True,
                threads=True,
                progress=progress,
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
            logger.error(
                f"Erro ao obter dados de preço para {symbols}: {e}", exc_info=True
            )
            return pd.DataFrame()

    @retry(max_attempts=settings.fetcher.YAHOO_RETRIES)
    @rate_limit(calls_per_minute=settings.fetcher.RATE_LIMIT_REQUESTS * 2)
    @timeout(seconds=settings.fetcher.YAHOO_TIMEOUT * 2)
    @validate_tickers()
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
        """Obtém dados históricos de preço de um ou mais ativos."""

        if settings.DEBUG:
            progress = True
        else:
            progress = False

        try:
            data = download(
                tickers=symbols,
                period=period,
                interval=interval,
                start=start,
                end=end,
                repair=True,
                threads=True,
                progress=progress,
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

        # Agrupa por tipo de operação para otimizar
        results = {}

        # Para preços, usa Tickers (mais eficiente)
        if "price" in data_types:
            prices = self.get_multiple_prices(symbols)
            for symbol in symbols:
                if symbol not in results:
                    results[symbol] = {}
                results[symbol]["price"] = prices.get(symbol)

        # Para outros tipos, usa threading
        other_types = [dt for dt in data_types if dt != "price"]
        if other_types:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Para cada símbolo
                for symbol in symbols:
                    if symbol not in results:
                        results[symbol] = {}

                    # Para cada tipo de dado restante
                    for data_type in other_types:
                        if data_type == "info":
                            future = executor.submit(self.get_ticker_info, symbol)
                        elif data_type == "dividend_yield":
                            future = executor.submit(self.get_dividend_yield, symbol)
                        elif data_type == "historical":
                            future = executor.submit(
                                self.get_historical_data, symbol, period="1mo"
                            )
                        else:
                            continue

                        try:
                            result = future.result(timeout=self.timeout)
                            results[symbol][data_type] = result
                        except Exception as e:
                            logger.error(
                                f"Erro ao obter {data_type} para {symbol}: {e}"
                            )
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
