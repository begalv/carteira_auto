"""Fetcher do Banco Central do Brasil (BCB) — API SGS.

Séries do SGS (Sistema Gerenciador de Séries Temporais):
    - SELIC (432): Taxa Selic meta — % a.a.
    - CDI (12): Taxa CDI — % a.d.
    - IPCA (433): IPCA variação mensal — %
    - PTAX compra (10813): Dólar PTAX compra — R$
    - PTAX venda (1): Dólar PTAX venda — R$
    - IGP-M (189): IGP-M variação mensal — %
    - TR (226): Taxa Referencial — % a.m.
    - INPC (188): INPC variação mensal — %
    - Poupança (25): Rendimento poupança — % a.m.

API: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json
Formato de data: DD/MM/YYYY
Resposta: [{"data": "DD/MM/YYYY", "valor": "12.25"}, ...]
Sem autenticação. Sem rate limit documentado (usar 30 req/min por segurança).
"""

from datetime import date, timedelta

import pandas as pd
import requests

from carteira_auto.config import settings
from carteira_auto.config.constants import constants
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
    rate_limit,
    retry,
)

logger = get_logger(__name__)


class BCBFetcher:
    """Fetcher para dados do Banco Central do Brasil via API SGS."""

    def __init__(self):
        self._base_url = settings.bcb.BASE_URL
        self._timeout = settings.bcb.TIMEOUT
        self._series = constants.BCB_SERIES_CODES

    # ============================================================================
    # MÉTODOS PÚBLICOS — INDICADORES ESPECÍFICOS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_selic(self, period_days: int = 365) -> pd.DataFrame:
        """Taxa Selic meta (% a.a.)."""
        return self._fetch_series("selic", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_cdi(self, period_days: int = 365) -> pd.DataFrame:
        """Taxa CDI (% a.d.)."""
        return self._fetch_series("cdi", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ipca(self, period_days: int = 365) -> pd.DataFrame:
        """IPCA — variação mensal (%)."""
        return self._fetch_series("ipca", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax(self, period_days: int = 30) -> pd.DataFrame:
        """Dólar PTAX compra (R$)."""
        return self._fetch_series("ptax_compra", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_igpm(self, period_days: int = 365) -> pd.DataFrame:
        """IGP-M — variação mensal (%)."""
        return self._fetch_series("igpm", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_tr(self, period_days: int = 365) -> pd.DataFrame:
        """Taxa Referencial (% a.m.)."""
        return self._fetch_series("tr", period_days)

    # ============================================================================
    # MÉTODOS PÚBLICOS — GENÉRICOS
    # ============================================================================

    @log_execution
    def get_indicator(
        self,
        series_code: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Busca qualquer série do SGS por código.

        Args:
            series_code: Código da série no SGS.
            start_date: Data inicial (default: 1 ano atrás).
            end_date: Data final (default: hoje).

        Returns:
            DataFrame com colunas ['data', 'valor'].
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        return self._fetch_raw(series_code, start_date, end_date)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_all_indicators(self) -> dict[str, pd.DataFrame]:
        """Busca todos os indicadores configurados.

        Returns:
            Dict {nome_indicador: DataFrame}.
        """
        results = {}
        for name, code in self._series.items():
            try:
                df = self._fetch_series(name)
                results[name] = df
                logger.debug(f"BCB {name}: {len(df)} registros")
            except Exception as e:
                logger.warning(f"Falha ao buscar BCB {name} (código {code}): {e}")
                results[name] = pd.DataFrame(columns=["data", "valor"])
        return results

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_latest_values(self) -> dict[str, float | None]:
        """Retorna o valor mais recente de cada indicador.

        Returns:
            Dict {nome_indicador: valor_float | None}.
        """
        results: dict[str, float | None] = {}
        for name in self._series:
            try:
                df = self._fetch_series(name, period_days=30)
                if not df.empty:
                    results[name] = df["valor"].iloc[-1]
                else:
                    results[name] = None
            except Exception as e:
                logger.warning(f"Falha ao buscar último valor BCB {name}: {e}")
                results[name] = None
        return results

    # ============================================================================
    # INTERNOS
    # ============================================================================

    def _fetch_series(self, name: str, period_days: int = 365) -> pd.DataFrame:
        """Busca uma série por nome configurado."""
        code = self._series.get(name)
        if code is None:
            raise ValueError(
                f"Série '{name}' não configurada. "
                f"Disponíveis: {list(self._series.keys())}"
            )

        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        return self._fetch_raw(code, start_date, end_date)

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_raw(
        self, series_code: int, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Faz a requisição HTTP ao SGS e retorna DataFrame.

        API: GET /dados/serie/bcdata.sgs.{code}/dados?formato=json
             &dataInicial=DD/MM/YYYY&dataFinal=DD/MM/YYYY
        """
        url = self._base_url.format(code=series_code)
        params = {
            "formato": "json",
            "dataInicial": start_date.strftime("%d/%m/%Y"),
            "dataFinal": end_date.strftime("%d/%m/%Y"),
        }

        logger.debug(f"BCB SGS: série {series_code} de {start_date} a {end_date}")

        response = requests.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()

        data = response.json()

        if not data:
            logger.warning(f"Série {series_code}: sem dados no período")
            return pd.DataFrame(columns=["data", "valor"])

        df = pd.DataFrame(data)

        # Converte tipos
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

        # Remove NaN
        df = df.dropna(subset=["valor"])

        logger.debug(f"Série {series_code}: {len(df)} registros retornados")
        return df
