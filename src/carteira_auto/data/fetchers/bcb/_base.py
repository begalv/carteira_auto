"""Base do BCBFetcher — config, logger e internals SGS.

Contém a infraestrutura compartilhada por todos os submódulos do BCBFetcher:
- Configuração (settings.bcb, constants)
- Logger
- Motor SGS dual: bcb.sgs (primário) → HTTP SGS (fallback)
"""

from datetime import date, timedelta

import pandas as pd
import requests

from carteira_auto.config import settings
from carteira_auto.config.constants import constants
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    rate_limit,
    retry,
)

logger = get_logger(__name__)


class BCBBaseMixin:
    """Infraestrutura base compartilhada do BCBFetcher.

    Fornece:
        - Configuração via settings.bcb
        - Constantes via constants.BCB_SERIES_CODES
        - Motor SGS dual (bcb.sgs → HTTP fallback)
        - Logger centralizado
    """

    def __init__(self) -> None:
        self._base_url = settings.bcb.BASE_URL
        self._timeout = settings.bcb.TIMEOUT
        self._series = constants.BCB_SERIES_CODES

    # =========================================================================
    # INTERNOS — SGS (bcb.sgs primário → HTTP fallback)
    # =========================================================================

    def _fetch_sgs_series(self, name: str, period_days: int = 5 * 365) -> pd.DataFrame:
        """Busca série SGS por nome configurado. Motor: bcb.sgs → HTTP fallback."""
        code = self._series.get(name)
        if code is None:
            raise ValueError(
                f"Série '{name}' não configurada. "
                f"Disponíveis: {list(self._series.keys())}"
            )
        end_dt = date.today()
        start_dt = end_dt - timedelta(days=period_days)
        return self._fetch_sgs_raw(code, start_dt, end_dt)

    def _fetch_sgs_raw(
        self, series_code: int, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca série SGS por código. Tenta bcb.sgs; fallback para HTTP."""
        try:
            return self._fetch_via_bcb_sgs(series_code, start_date, end_date)
        except Exception as e:
            logger.warning(
                f"bcb.sgs falhou para série {series_code}: {e}. "
                "Usando fallback HTTP SGS."
            )
            return self._fetch_raw(series_code, start_date, end_date)

    def _fetch_sgs_last(self, series_code: int, last_n: int) -> pd.DataFrame:
        """Busca últimos N registros de uma série SGS via bcb.sgs.

        Otimização para get_latest_values() — evita buscar período inteiro
        quando só precisa do(s) último(s) valor(es).
        """
        try:
            return self._fetch_via_bcb_sgs_last(series_code, last_n)
        except Exception as e:
            logger.warning(
                f"bcb.sgs(last={last_n}) falhou para série {series_code}: {e}. "
                "Usando fallback com period_days=30."
            )
            end_dt = date.today()
            start_dt = end_dt - timedelta(days=30)
            return self._fetch_raw(series_code, start_dt, end_dt)

    @retry(max_attempts=2, delay=0.5)
    def _fetch_via_bcb_sgs(
        self, series_code: int, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca série via bcb.sgs (motor primário).

        Tenta 2x com backoff de 0.5s antes de propagar a exceção para o
        fallback HTTP em _fetch_sgs_raw(). Erros transientes (timeout, 503)
        são recuperados sem acionar o HTTP.
        """
        from bcb import sgs

        df = sgs.get(
            {"valor": series_code},
            start=start_date,
            end=end_date,
        )

        if df is None or df.empty:
            return pd.DataFrame(columns=["data", "valor"])

        df = df.reset_index()
        df.columns = ["data", "valor"]
        df["data"] = pd.to_datetime(df["data"])
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"])

        logger.debug(f"bcb.sgs série {series_code}: {len(df)} registros")
        return df

    @retry(max_attempts=2, delay=0.5)
    def _fetch_via_bcb_sgs_last(self, series_code: int, last_n: int) -> pd.DataFrame:
        """Busca últimos N registros via bcb.sgs(last=N).

        Usado por get_latest_values() para eficiência — evita buscar
        período inteiro quando só precisa do último valor.
        """
        from bcb import sgs

        df = sgs.get({"valor": series_code}, last=last_n)

        if df is None or df.empty:
            return pd.DataFrame(columns=["data", "valor"])

        df = df.reset_index()
        df.columns = ["data", "valor"]
        df["data"] = pd.to_datetime(df["data"])
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"])

        logger.debug(
            f"bcb.sgs série {series_code} (last={last_n}): {len(df)} registros"
        )
        return df

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_raw(
        self, series_code: int, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca série via HTTP SGS (fallback).

        API: GET /dados/serie/bcdata.sgs.{code}/dados?formato=json
             &dataInicial=DD/MM/YYYY&dataFinal=DD/MM/YYYY
        """
        url = self._base_url.format(code=series_code)
        params = {
            "formato": "json",
            "dataInicial": start_date.strftime("%d/%m/%Y"),
            "dataFinal": end_date.strftime("%d/%m/%Y"),
        }

        logger.debug(f"BCB HTTP SGS: série {series_code} de {start_date} a {end_date}")
        response = requests.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()

        data = response.json()
        if not data:
            logger.warning(f"Série {series_code}: sem dados no período")
            return pd.DataFrame(columns=["data", "valor"])

        df = pd.DataFrame(data)
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"])

        logger.debug(f"HTTP SGS {series_code}: {len(df)} registros")
        return df
