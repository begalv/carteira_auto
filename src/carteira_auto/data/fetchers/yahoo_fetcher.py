"""Fetcher para dados do Yahoo Finance."""

from typing import Optional

import pandas as pd
import yfinance as yf

from carteira_auto.config.settings import settings
from carteira_auto.utils.logger import logger


class YahooFinanceFetcher:
    """Classe para buscar dados do Yahoo Finance."""

    def __init__(self):
        # Importar settings aqui para evitar importação circular
        self.timeout = settings.fetcher.YAHOO_TIMEOUT
        self.retries = settings.fetcher.YAHOO_RETRIES

    def get_ticker_data(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """Busca dados históricos para um símbolo.

        Args:
            symbol: Ticker (ex: 'PETR4.SA', 'AAPL')
            period: Período ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
            interval: Intervalo ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')

        Returns:
            DataFrame com dados históricos ou None em caso de erro.
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                logger.warning(f"Nenhum dado encontrado para {symbol}")
                return None

            logger.debug(f"Dados obtidos para {symbol}: {len(hist)} registros")
            return hist

        except Exception as e:
            logger.error(f"Erro ao buscar dados para {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Obtém o preço atual de um ativo.

        Args:
            symbol: Ticker

        Returns:
            Preço atual ou None em caso de erro.
        """
        try:
            ticker = yf.Ticker(symbol)
            # Usa info para pegar o preço atual
            info = ticker.info

            # Tenta diferentes campos de preço
            price_fields = [
                "regularMarketPrice",
                "currentPrice",
                "ask",
                "bid",
                "previousClose",
            ]

            for field in price_fields:
                price = info.get(field)
                if price is not None:
                    logger.debug(f"Preço atual de {symbol}: {price} (campo: {field})")
                    return float(price)

            # Fallback: último preço do histórico recente
            hist = ticker.history(period="1d", interval="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
                logger.debug(f"Preço atual de {symbol} (via histórico): {price}")
                return float(price)

            logger.warning(f"Nenhum preço encontrado para {symbol}")
            return None

        except Exception as e:
            logger.error(f"Erro ao obter preço para {symbol}: {e}")
            return None

    def get_multiple_prices(self, symbols: list[str]) -> dict[str, Optional[float]]:
        """Obtém preços atuais para múltiplos símbolos.

        Args:
            symbols: Lista de tickers

        Returns:
            Dicionário {símbolo: preço}
        """
        results = {}
        for symbol in symbols:
            price = self.get_current_price(symbol)
            results[symbol] = price

        return results

    def get_dividend_yield(self, symbol: str) -> Optional[float]:
        """Obtém o dividend yield de um ativo.

        Args:
            symbol: Ticker

        Returns:
            Dividend yield (em decimal) ou None.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Tenta diferentes campos
            dy_fields = [
                "dividendYield",
                "trailingAnnualDividendYield",
                "forwardDividendYield",
            ]

            for field in dy_fields:
                dy = info.get(field)
                if dy is not None:
                    return float(dy)

            return None

        except Exception as e:
            logger.error(f"Erro ao obter dividend yield para {symbol}: {e}")
            return None

    def validate_symbol(self, symbol: str) -> bool:
        """Valida se um símbolo existe no Yahoo Finance.

        Args:
            symbol: Ticker

        Returns:
            True se válido, False caso contrário.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Se info estiver vazio ou conter erro, símbolo é inválido
            if not info or "regularMarketPrice" not in info:
                return False

            return True

        except Exception:
            return False
