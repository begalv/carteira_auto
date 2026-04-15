"""Fetcher do FRED — Federal Reserve Economic Data.

Portal: https://fred.stlouisfed.org
API: https://api.stlouisfed.org/fred/
Docs: https://fred.stlouisfed.org/docs/api/fred/
Auth: API key via query param `api_key`. Chave gratuita em https://fred.stlouisfed.org/docs/api/api_key.html

Séries disponíveis (amostra relevante para carteira BR):
    Juros e Inflação:
        DFF        — Fed Funds Rate (diária)
        CPIAUCSL   — CPI (mensal, índice)
        PCEPILFE   — Core PCE (mensal, YoY)
        DFII10     — TIPS 10Y real yield (diária)

    Curva de Juros US:
        DGS3MO     — Treasury 3 meses
        DGS2       — Treasury 2 anos
        DGS10      — Treasury 10 anos
        DGS30      — Treasury 30 anos
        T10Y2Y     — Spread 10Y-2Y (indicador de recessão)

    Atividade Econômica:
        GDP        — PIB nominal EUA (trimestral)
        GDPC1      — PIB real EUA (trimestral)
        UNRATE     — Taxa de desemprego (mensal)
        INDPRO     — Produção industrial (mensal)

    Mercados / Risco:
        VIXCLS     — VIX (diária)
        BAMLH0A0HYM2  — High yield spread (OAS, diária)
        T10YIE     — Breakeven inflação 10Y

    Câmbio:
        DEXBZUS    — BRL/USD (diária)
        DEXUSEU    — EUR/USD (diária)
        DEXCHUS    — CNY/USD (diária)

Fluxo típico:
    1. Configurar FRED_API_KEY no .env
    2. fetcher.get_series("DFF") → DataFrame com date + value
    3. fetcher.get_macro_bundle() → dict {serie_id: DataFrame}
"""

from __future__ import annotations

from datetime import date

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

# Subconjunto mínimo para análise macro (bundle padrão)
FRED_MACRO_BUNDLE = [
    "DFF",  # Fed Funds — juros referência global
    "DGS10",  # Treasury 10Y — piso de risco
    "T10Y2Y",  # Spread — sinal de recessão
    "VIXCLS",  # Volatilidade — medo do mercado
    "CPIAUCSL",  # Inflação US — referência para política
    "DEXBZUS",  # BRL/USD — câmbio crítico para carteira BR
]


class FREDFetcher:
    """Fetcher para séries econômicas do FRED (Federal Reserve).

    Requer API key gratuita configurada em settings.API_KEYS["fred"]
    ou variável de ambiente FRED_API_KEY.

    Sem chave, o fetcher loga um aviso e falha graciosamente
    (útil para testes com mock).

    Uso:
        fetcher = FREDFetcher()

        # Série individual
        df = fetcher.get_series("DFF")  # Fed Funds Rate

        # Bundle macro completo
        bundle = fetcher.get_macro_bundle()

        # Múltiplas séries customizadas
        dfs = fetcher.get_multiple_series(["DFF", "DGS10", "T10Y2Y"])
    """

    def __init__(self) -> None:
        self._base_url = settings.fred.BASE_URL
        self._timeout = settings.fred.TIMEOUT
        self._api_key = settings.API_KEYS.get("fred")

        if not self._api_key:
            logger.warning(
                "FRED API key não configurada. "
                "Obtenha uma chave gratuita em https://fred.stlouisfed.org/docs/api/api_key.html "
                "e defina FRED_API_KEY no .env"
            )

    # ============================================================================
    # SÉRIES INDIVIDUAIS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_series(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Retorna série temporal do FRED como DataFrame.

        Args:
            series_id: Código da série (ex: "DFF", "DGS10", "VIXCLS").
            start_date: Data inicial no formato "YYYY-MM-DD". Default: 10 anos atrás.
            end_date: Data final no formato "YYYY-MM-DD". Default: hoje.

        Returns:
            DataFrame com colunas: date (datetime), value (float), series_id (str).
            Valores "." (missing do FRED) são convertidos para NaN e removidos.

        Raises:
            PermissionError: API key inválida ou ausente.
            requests.HTTPError: Série não encontrada (404).
        """
        if not self._api_key:
            raise PermissionError(
                "FRED API key não configurada. Defina FRED_API_KEY no .env"
            )

        if start_date is None:
            # Default: 10 anos de histórico
            start_year = date.today().year - 10
            start_date = f"{start_year}-01-01"
        if end_date is None:
            end_date = date.today().isoformat()

        params = {
            "series_id": series_id,
            "observation_start": start_date,
            "observation_end": end_date,
            "api_key": self._api_key,
            "file_type": "json",
        }

        logger.debug(f"FRED: buscando série {series_id} ({start_date} → {end_date})")
        response = self._get(params)

        observations = response.get("observations", [])
        if not observations:
            logger.warning(f"FRED: série {series_id} sem observações")
            return pd.DataFrame(columns=["date", "value", "series_id"])

        df = pd.DataFrame(observations)

        # Renomeia e converte tipos
        df = df[["date", "value"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        # FRED usa "." para valores ausentes
        df["value"] = pd.to_numeric(
            df["value"].replace(".", float("nan")), errors="coerce"
        )
        df["series_id"] = series_id

        df = df.dropna(subset=["value"]).reset_index(drop=True)

        logger.info(
            f"FRED: {series_id} — {len(df)} observações ({start_date} → {end_date})"
        )
        return df

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_series_info(self, series_id: str) -> dict:
        """Metadados de uma série FRED (nome, unidade, frequência, última atualização).

        Args:
            series_id: Código da série (ex: "DFF").

        Returns:
            Dict com title, units, frequency, last_updated, etc.
        """
        if not self._api_key:
            raise PermissionError(
                "FRED API key não configurada. Defina FRED_API_KEY no .env"
            )

        params = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
        }

        base_info_url = "https://api.stlouisfed.org/fred/series"
        logger.debug(f"FRED: metadados de {series_id}")
        response = self._get(params, url_override=base_info_url)
        serieses = response.get("seriess", [])
        return serieses[0] if serieses else {}

    # ============================================================================
    # MÚLTIPLAS SÉRIES
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_multiple_series(
        self,
        series_ids: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Busca múltiplas séries FRED em paralelo (sequencial com cache).

        Args:
            series_ids: Lista de códigos de série.
            start_date: Data inicial (YYYY-MM-DD).
            end_date: Data final (YYYY-MM-DD).

        Returns:
            Dict {series_id: DataFrame} para cada série com dados.
            Séries com erro são omitidas com log de aviso.
        """
        result: dict[str, pd.DataFrame] = {}
        for sid in series_ids:
            try:
                df = self.get_series(sid, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    result[sid] = df
            except Exception as e:
                logger.warning(f"FRED: erro ao buscar série {sid} — {e}")
        return result

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_macro_bundle(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Bundle macro padrão: Fed Funds, Treasury 10Y, Spread, VIX, CPI, BRL/USD.

        Conjunto mínimo para análise de ambiente macro global e impacto
        na carteira BR. Inclui:
        - DFF: Juros do Fed (aperto/afrouxamento monetário)
        - DGS10: Treasury 10Y (piso de risco global)
        - T10Y2Y: Spread 10Y-2Y (sinal de recessão)
        - VIXCLS: VIX (volatilidade / medo)
        - CPIAUCSL: Inflação EUA
        - DEXBZUS: BRL/USD

        Args:
            start_date: Data inicial (YYYY-MM-DD).
            end_date: Data final (YYYY-MM-DD).

        Returns:
            Dict {series_id: DataFrame} para as 6 séries do bundle.
        """
        return self.get_multiple_series(
            FRED_MACRO_BUNDLE, start_date=start_date, end_date=end_date
        )

    # ============================================================================
    # CONVENIÊNCIA — SÉRIES INDIVIDUAIS TIPADAS
    # ============================================================================

    def get_fed_funds_rate(self) -> pd.DataFrame:
        """Fed Funds Rate efetiva (DFF) — diária."""
        return self.get_series("DFF")

    def get_treasury_10y(self) -> pd.DataFrame:
        """Treasury yield 10 anos (DGS10) — diária."""
        return self.get_series("DGS10")

    def get_treasury_2y(self) -> pd.DataFrame:
        """Treasury yield 2 anos (DGS2) — diária."""
        return self.get_series("DGS2")

    def get_yield_curve_spread(self) -> pd.DataFrame:
        """Spread 10Y-2Y (T10Y2Y) — indicador de inversão de curva."""
        return self.get_series("T10Y2Y")

    def get_vix(self) -> pd.DataFrame:
        """VIX — índice de volatilidade esperada do S&P 500 (VIXCLS) — diária."""
        return self.get_series("VIXCLS")

    def get_us_cpi(self) -> pd.DataFrame:
        """CPI EUA (CPIAUCSL) — mensal, base 1982-84=100."""
        return self.get_series("CPIAUCSL")

    def get_core_pce(self) -> pd.DataFrame:
        """Core PCE (PCEPILFE) — preferido do Fed para meta de inflação."""
        return self.get_series("PCEPILFE")

    def get_brl_usd(self) -> pd.DataFrame:
        """Taxa de câmbio BRL/USD (DEXBZUS) — diária."""
        return self.get_series("DEXBZUS")

    def get_us_gdp(self, real: bool = True) -> pd.DataFrame:
        """PIB dos EUA trimestral.

        Args:
            real: Se True, retorna PIB real (GDPC1); se False, nominal (GDP).
        """
        series_id = "GDPC1" if real else "GDP"
        return self.get_series(series_id)

    def get_us_unemployment(self) -> pd.DataFrame:
        """Taxa de desemprego EUA (UNRATE) — mensal."""
        return self.get_series("UNRATE")

    def get_high_yield_spread(self) -> pd.DataFrame:
        """High yield spread OAS (BAMLH0A0HYM2) — indicador de apetite a risco."""
        return self.get_series("BAMLH0A0HYM2")

    def get_breakeven_inflation(self) -> pd.DataFrame:
        """Breakeven inflação 10Y (T10YIE) — expectativa de inflação implícita."""
        return self.get_series("T10YIE")

    # ---- Curva Treasuries (complementares) ----

    def get_treasury_3m(self) -> pd.DataFrame:
        """Treasury yield 3 meses (DGS3MO) — ponta curta da curva."""
        return self.get_series("DGS3MO")

    def get_treasury_30y(self) -> pd.DataFrame:
        """Treasury yield 30 anos (DGS30) — ponta longa da curva."""
        return self.get_series("DGS30")

    def get_tips_real_yield(self) -> pd.DataFrame:
        """TIPS 10Y real yield (DFII10) — juros real dos EUA."""
        return self.get_series("DFII10")

    # ---- Atividade econômica (complementares) ----

    def get_industrial_production(self) -> pd.DataFrame:
        """Produção industrial EUA (INDPRO) — proxy de atividade manufatureira."""
        return self.get_series("INDPRO")

    def get_nonfarm_payrolls(self) -> pd.DataFrame:
        """Nonfarm Payrolls (PAYEMS) — criação líquida de empregos."""
        return self.get_series("PAYEMS")

    def get_consumer_sentiment(self) -> pd.DataFrame:
        """Sentimento do consumidor Michigan (UMCSENT) — confiança do consumidor."""
        return self.get_series("UMCSENT")

    # ---- Câmbio (complementares) ----

    def get_eur_usd(self) -> pd.DataFrame:
        """Taxa de câmbio EUR/USD (DEXUSEU) — par mais negociado do mundo."""
        return self.get_series("DEXUSEU")

    def get_cny_usd(self) -> pd.DataFrame:
        """Taxa de câmbio CNY/USD (DEXCHUS) — câmbio China."""
        return self.get_series("DEXCHUS")

    def get_dollar_index(self) -> pd.DataFrame:
        """Índice do dólar ponderado por comércio (DTWEXBGS) — força global do USD."""
        return self.get_series("DTWEXBGS")

    # ---- Commodities ----

    def get_wti_oil(self) -> pd.DataFrame:
        """Petróleo WTI (DCOILWTICO) — referência global, impacta Petrobras."""
        return self.get_series("DCOILWTICO")

    def get_gold_price(self) -> pd.DataFrame:
        """Ouro London Fix (GOLDAMGBD228NLBM) — ativo de refúgio."""
        return self.get_series("GOLDAMGBD228NLBM")

    @staticmethod
    def list_series() -> dict[str, dict[str, str]]:
        """Lista todas as séries FRED disponíveis neste fetcher.

        Returns:
            Dict {series_id: {nome, unidade, frequencia}} de séries suportadas.
            Fonte canônica: Constants.FRED_SERIES em config/constants.py.
        """
        return dict(constants.FRED_SERIES)

    # ============================================================================
    # INTERNOS
    # ============================================================================

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=120)
    def _get(self, params: dict, url_override: str | None = None) -> dict:
        """Faz GET à API FRED e retorna JSON.

        Args:
            params: Query parameters (inclui api_key, series_id, etc.).
            url_override: URL alternativa (para endpoints além de observations).

        Returns:
            Resposta JSON como dict.

        Raises:
            PermissionError: Chave inválida (400/403).
            requests.HTTPError: Outros erros HTTP.
        """
        url = url_override or self._base_url
        logger.debug(f"FRED: GET {url} series={params.get('series_id', '')}")

        response = requests.get(url, params=params, timeout=self._timeout)

        if response.status_code in (400, 403):
            raise PermissionError(
                f"FRED API: erro de autenticação (HTTP {response.status_code}). "
                "Verifique FRED_API_KEY no .env"
            )
        if response.status_code == 404:
            series_id = params.get("series_id", "?")
            raise requests.HTTPError(
                f"FRED: série '{series_id}' não encontrada (404)",
                response=response,
            )

        response.raise_for_status()
        return response.json()
