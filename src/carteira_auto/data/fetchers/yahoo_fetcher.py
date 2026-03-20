"""Fetcher otimizado para dados do Yahoo Finance."""

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Busca dados do Yahoo Finance com cache, retry e paralelismo."""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or min(32, os.cpu_count() + 4)
        self.timeout = settings.yahoo.TIMEOUT
        self.retries = settings.yahoo.RETRIES
        self.rate_limit_calls = settings.yahoo.RATE_LIMIT

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

    # ========================================================================
    # NORMALIZAÇÃO DE TICKERS
    # ========================================================================

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
        for pattern in constants.VALID_TICKER_PATTERNS.values():
            if re.match(pattern, ticker):
                return f"{ticker}.SA"
        # Padrão genérico B3: letras/dígitos terminando em 2 dígitos
        if re.match(r"^[A-Z0-9]{4,6}\d{2}$", ticker):
            return f"{ticker}.SA"
        return ticker

    # ========================================================================
    # DADOS HISTÓRICOS (batch via yf.download)
    # ========================================================================

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT * 2)
    @timeout(seconds=settings.yahoo.TIMEOUT * 2)
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

    # ========================================================================
    # INFORMAÇÕES DO TICKER (funções específicas e leves)
    # ========================================================================

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_basic_info(self, symbol: str) -> Optional[dict[str, Any]]:
        """Obtém informações básicas: preço, setor, nome, market cap, etc."""
        try:
            return Ticker(symbol).info or None
        except Exception as e:
            logger.error(f"Erro ao obter info de {symbol}: {e}")
            return None

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT * 2)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_financials(self, symbol: str) -> Optional[dict[str, Any]]:
        """Obtém dados financeiros: DRE, balanço, fluxo de caixa."""
        try:
            ticker = Ticker(symbol)
            result = {
                "financials": ticker.financials,
                "quarterly_financials": ticker.quarterly_financials,
                "balance_sheet": ticker.balance_sheet,
                "quarterly_balance_sheet": ticker.quarterly_balance_sheet,
                "cashflow": ticker.cashflow,
                "quarterly_cashflow": ticker.quarterly_cashflow,
            }
            return {
                k: v
                for k, v in result.items()
                if v is not None and (not hasattr(v, "empty") or not v.empty)
            }
        except Exception as e:
            logger.error(f"Erro ao obter financials de {symbol}: {e}")
            return None

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_dividends(self, symbol: str) -> Optional[dict[str, Any]]:
        """Obtém histórico de dividendos, splits e ações corporativas."""
        try:
            ticker = Ticker(symbol)
            result = {
                "dividends": ticker.dividends,
                "splits": ticker.splits,
                "capital_gains": ticker.capital_gains,
                "actions": ticker.actions,
            }
            return {
                k: v
                for k, v in result.items()
                if v is not None and (not hasattr(v, "empty") or not v.empty)
            }
        except Exception as e:
            logger.error(f"Erro ao obter dividendos de {symbol}: {e}")
            return None

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_earnings(self, symbol: str) -> Optional[dict[str, Any]]:
        """Obtém dados de lucros e estimativas."""
        try:
            ticker = Ticker(symbol)
            result = {
                "earnings": ticker.earnings,
                "quarterly_earnings": ticker.quarterly_earnings,
                "earnings_dates": ticker.earnings_dates,
                "earnings_history": ticker.earnings_history,
            }
            return {
                k: v
                for k, v in result.items()
                if v is not None and (not hasattr(v, "empty") or not v.empty)
            }
        except Exception as e:
            logger.error(f"Erro ao obter earnings de {symbol}: {e}")
            return None

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_holders(self, symbol: str) -> Optional[dict[str, Any]]:
        """Obtém dados de acionistas e insiders."""
        try:
            ticker = Ticker(symbol)
            result = {
                "major_holders": ticker.major_holders,
                "institutional_holders": ticker.institutional_holders,
                "mutualfund_holders": ticker.mutualfund_holders,
                "insider_transactions": ticker.insider_transactions,
                "insider_purchases": ticker.insider_purchases,
                "insider_roster_holders": ticker.insider_roster_holders,
            }
            return {
                k: v
                for k, v in result.items()
                if v is not None and (not hasattr(v, "empty") or not v.empty)
            }
        except Exception as e:
            logger.error(f"Erro ao obter holders de {symbol}: {e}")
            return None

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_recommendations(self, symbol: str) -> Optional[dict[str, Any]]:
        """Obtém recomendações de analistas e price targets."""
        try:
            ticker = Ticker(symbol)
            result = {
                "recommendations": ticker.recommendations,
                "recommendations_summary": ticker.recommendations_summary,
                "upgrades_downgrades": ticker.upgrades_downgrades,
                "analyst_price_target": ticker.analyst_price_target,
                "growth_estimates": ticker.growth_estimates,
            }
            return {
                k: v
                for k, v in result.items()
                if v is not None and (not hasattr(v, "empty") or not v.empty)
            }
        except Exception as e:
            logger.error(f"Erro ao obter recommendations de {symbol}: {e}")
            return None

    # ========================================================================
    # DIVIDENDOS E YIELD
    # ========================================================================

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @validate_tickers
    @cache_by_ticker(ttl_seconds=86400)  # 24h
    def get_dividend_yield(self, symbol: str) -> Optional[float]:
        """Obtém o dividend yield de um ativo."""
        try:
            ticker = Ticker(symbol)
            info = ticker.info

            for field in [
                "dividendYield",
                "trailingAnnualDividendYield",
                "forwardDividendYield",
                "yield",
            ]:
                dy = info.get(field)
                if dy is not None:
                    logger.info(f"Dividend yield de {symbol}: {float(dy):.2%}")
                    return float(dy)

            # Calcula a partir do histórico de dividendos
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

    # ========================================================================
    # PREÇO INDIVIDUAL E MÚLTIPLO
    # ========================================================================

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
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

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT * 2)
    @log_execution
    def get_multiple_prices(self, symbols: list[str]) -> dict[str, Optional[float]]:
        """Obtém preços atuais de múltiplos ativos via yf.download.

        Aceita tickers originais (ex: PETR4) — normalização e filtragem
        são feitas internamente. Resultados retornados com chaves originais.
        """
        if not symbols:
            return {}

        eligible = [s for s in symbols if s not in constants.NON_YAHOO_TICKERS]
        skipped = {s: None for s in symbols if s in constants.NON_YAHOO_TICKERS}

        if not eligible:
            logger.warning("Nenhum ticker elegível para o Yahoo Finance")
            return skipped

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
                return dict.fromkeys(symbols)

            if len(yahoo_symbols) == 1:
                if "Close" in data.columns:
                    last_close = data["Close"].dropna().iloc[-1]
                    results[eligible[0]] = float(last_close)
                else:
                    results[eligible[0]] = None
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
            return dict.fromkeys(symbols)

        for s in eligible:
            if s not in results:
                results[s] = None

        results.update(skipped)

        logger.info(
            f"Preços obtidos: {sum(1 for v in results.values() if v is not None)}"
            f"/{len(symbols)} tickers"
        )
        return results

    # ========================================================================
    # BATCH — busca múltiplos dados de múltiplos tickers em paralelo
    # ========================================================================

    @retry(max_attempts=settings.yahoo.RETRIES)
    @timeout(seconds=settings.yahoo.TIMEOUT * 3)
    @log_execution
    def get_batch_info(
        self,
        symbols: list[str],
        fields: Optional[list[str]] = None,
    ) -> dict[str, dict[str, Any]]:
        """Busca múltiplos tipos de dados para múltiplos tickers em paralelo.

        Cada thread cria UM Ticker() e extrai todos os fields pedidos,
        evitando múltiplas instanciações por ticker.

        Args:
            symbols: Lista de tickers.
            fields: Dados a buscar. Opções: "info", "dividends", "financials",
                    "earnings", "holders", "recommendations".
                    Default: ["info", "dividends"]
        """
        if fields is None:
            fields = ["info", "dividends"]

        if not symbols:
            return {}

        field_extractors = {
            "info": lambda t: t.info,
            "dividends": lambda t: {
                "dividends": t.dividends,
                "splits": t.splits,
                "actions": t.actions,
            },
            "financials": lambda t: {
                "financials": t.financials,
                "balance_sheet": t.balance_sheet,
                "cashflow": t.cashflow,
            },
            "earnings": lambda t: {
                "earnings": t.earnings,
                "quarterly_earnings": t.quarterly_earnings,
            },
            "holders": lambda t: {
                "major_holders": t.major_holders,
                "institutional_holders": t.institutional_holders,
            },
            "recommendations": lambda t: {
                "recommendations": t.recommendations,
                "analyst_price_target": t.analyst_price_target,
            },
        }

        def _fetch_single(symbol: str) -> dict[str, Any]:
            """Cria UM Ticker e extrai todos os fields pedidos."""
            ticker = Ticker(symbol)
            result = {}
            for field in fields:
                extractor = field_extractors.get(field)
                if extractor:
                    try:
                        data = extractor(ticker)
                        # Filtra valores vazios em dicts aninhados
                        if isinstance(data, dict):
                            data = {
                                k: v
                                for k, v in data.items()
                                if v is not None
                                and (not hasattr(v, "empty") or not v.empty)
                            }
                        result[field] = data if data else None
                    except Exception as e:
                        logger.debug(f"Erro ao extrair {field} de {symbol}: {e}")
                        result[field] = None
            return result

        results: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_fetch_single, s): s for s in symbols}

            for future in as_completed(futures, timeout=self.timeout * 2):
                symbol = futures[future]
                try:
                    results[symbol] = future.result()
                except Exception as e:
                    logger.error(f"Erro no batch para {symbol}: {e}")
                    results[symbol] = dict.fromkeys(fields)

        logger.info(
            f"Batch info concluído: {len(results)}/{len(symbols)} tickers, "
            f"fields={fields}"
        )
        return results

    # ========================================================================
    # MERCADO, PESQUISA E CALENDÁRIO
    # ========================================================================

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=300)  # 5min
    def get_market_summary(self, market: str = "us") -> Optional[dict[str, Any]]:
        """Obtém resumo do mercado ('us', 'br', 'au', etc.)."""
        try:
            summary = Market(market).summary
            if not summary:
                logger.warning(f"Nenhum resumo de mercado para {market}")
                return None
            logger.info(f"Resumo do mercado {market}: {len(summary)} indicadores")
            return summary
        except Exception as e:
            logger.error(f"Erro ao obter resumo do mercado {market}: {e}")
            return None

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def search_tickers(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Busca tickers por nome ou símbolo."""
        try:
            results = Search(query).results
            if not results:
                logger.warning(f"Nenhum resultado para: {query}")
                return []
            return results[:limit]
        except Exception as e:
            logger.error(f"Erro na busca por '{query}': {e}")
            return []

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def get_market_calendar(self, days: int = 30) -> Optional[pd.DataFrame]:
        """Obtém calendário de eventos do mercado."""
        try:
            calendar_data = Calendars(days=days).events
            if calendar_data.empty:
                logger.warning("Nenhum evento de calendário encontrado")
                return None
            logger.debug(f"Calendário obtido: {len(calendar_data)} eventos")
            return calendar_data
        except Exception as e:
            logger.error(f"Erro ao obter calendário: {e}")
            return None

    # ========================================================================
    # SETORES E INDÚSTRIAS
    # ========================================================================

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def get_sector_performance(
        self, sector: str = "technology"
    ) -> Optional[dict[str, Any]]:
        """Obtém performance de um setor específico.

        Setores: 'communication_services', 'consumer_cyclical', 'consumer_defensive',
                 'energy', 'financial_services', 'healthcare', 'industrials',
                 'real_estate', 'technology', 'utilities', 'basic_materials'
        """
        try:
            sector_obj = yf.Sector(sector)
            if hasattr(sector_obj, "info") and sector_obj.info:
                return sector_obj.info
            logger.warning(f"Nenhuma informação para o setor {sector}")
            return None
        except Exception as e:
            logger.debug(f"Setor {sector} não disponível: {e}")
            return None

    @retry(max_attempts=settings.yahoo.RETRIES)
    @rate_limit(calls_per_minute=settings.yahoo.RATE_LIMIT)
    @timeout(seconds=settings.yahoo.TIMEOUT)
    @log_execution
    @cache_result(ttl_seconds=3600)  # 1h
    def get_industry_performance(
        self, industry: str = "software"
    ) -> Optional[dict[str, Any]]:
        """Obtém performance de uma indústria específica."""
        try:
            industry_obj = yf.Industry(industry)
            if hasattr(industry_obj, "info") and industry_obj.info:
                return industry_obj.info
            logger.warning(f"Nenhuma informação para a indústria {industry}")
            return None
        except Exception as e:
            logger.debug(f"Indústria {industry} não disponível: {e}")
            return None

    # ========================================================================
    # VALIDAÇÃO
    # ========================================================================

    @log_execution
    def validate_symbol(self, symbol: str) -> tuple[bool, str]:
        """Valida se um símbolo existe no Yahoo Finance."""
        try:
            is_valid, ticker_type = validate_ticker(symbol)
            if not is_valid:
                return False, f"Formato inválido: {ticker_type}"

            info = Ticker(symbol).info
            if not info or "symbol" not in info:
                return False, "Não encontrado no Yahoo Finance"

            return True, ticker_type

        except Exception as e:
            return False, f"Erro de validação: {str(e)}"
