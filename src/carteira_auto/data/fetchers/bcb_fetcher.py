"""Fetcher do Banco Central do Brasil (BCB) — API SGS.

Séries do SGS (Sistema Gerenciador de Séries Temporais):

    Taxas de juros:
        - SELIC meta (432)      : % a.a.  | Reuniões COPOM (~8×/ano)
        - CDI diário (12)       : % a.d.  | Divulgação diária (dias úteis)
        - TR (226)              : % a.m.  | Divulgação mensal

    Inflação:
        - IPCA mensal (433)     : %       | Divulgação ~9 dias após fim do mês
        - IGP-M mensal (189)    : %       | Divulgação ~último dia útil do mês
        - INPC mensal (188)     : %       | Divulgação ~9 dias após fim do mês

    Câmbio:
        - PTAX compra (10813)   : R$/USD  | Divulgação diária (dias úteis)
        - PTAX venda (1)        : R$/USD  | Divulgação diária (dias úteis)

    Poupança:
        - Poupança (25)         : % a.m.  | Divulgação mensal

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
    def get_selic(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa Selic meta — % a.a. | Reuniões COPOM (~8×/ano) | SGS 432.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.a.
        """
        return self._fetch_series("selic", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_cdi(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """CDI diário — % a.d. | Divulgação diária (dias úteis) | SGS 12.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.d.
            Para % a.a.: ((1 + valor/100) ** 252 - 1) * 100
        """
        return self._fetch_series("cdi", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ipca(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IPCA — variação mensal (%) | Divulgação ~9 dias após fim do mês | SGS 433.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
            Para acumulado 12m: ((1 + v/100).prod() - 1) * 100
        """
        return self._fetch_series("ipca", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax(self, period_days: int = 30) -> pd.DataFrame:
        """Dólar PTAX compra — R$ por USD | Dias úteis | SGS 10813.

        Args:
            period_days: Número de dias retroativos (default: 30 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$/USD.
        """
        return self._fetch_series("ptax_compra", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax_venda(self, period_days: int = 30) -> pd.DataFrame:
        """Dólar PTAX venda — R$ por USD | Dias úteis | SGS 1.

        Args:
            period_days: Número de dias retroativos (default: 30 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$/USD.
        """
        return self._fetch_series("ptax_venda", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_igpm(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IGP-M — variação mensal (%) | Divulgação ~último dia útil do mês | SGS 189.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_series("igpm", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_tr(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa Referencial (TR) — % a.m. | Divulgação mensal | SGS 226.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.m.
        """
        return self._fetch_series("tr", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_inpc(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """INPC — variação mensal (%) | Divulgação ~9 dias após fim do mês | SGS 188.

        Índice Nacional de Preços ao Consumidor — mede inflação para famílias
        com renda de 1 a 5 salários mínimos.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_series("inpc", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_poupanca(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Rendimento da poupança — % a.m. | Divulgação mensal | SGS 25.

        Desde maio/2012: TR + 0,5% a.m. quando Selic <= 8,5% a.a.;
        ou 70% Selic/252 + TR quando Selic > 8,5% a.a.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.m.
            Para % a.a.: ((1 + valor/100) ** 12 - 1) * 100
        """
        return self._fetch_series("poupanca", period_days)

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
        """Busca qualquer série do SGS por código numérico.

        Use este método para séries não cobertas pelos métodos específicos,
        ou para consultas com janelas de datas precisas.

        Exemplos de séries úteis (além das cobertas pelos métodos específicos):
            - 4390: IPCA-15 (prévia do IPCA mensal — %)
            - 7445: INCC (variação mensal — %)
            - 13521: Meta de inflação do CMN para o ano corrente (% a.a.)
            - 4175: Superávit/déficit primário do governo (R$ MM)
            - 13762: Resultado nominal do setor público (R$ MM)
            - 4051: Dívida líquida do setor público / PIB (%)
            - 7478: Balança comercial (saldo mensal em USD MM)
            - 3545: IBC-Br (proxy mensal do PIB — %)
            - 28750: Expectativa IPCA 12 meses à frente (Focus — %)
            - 28751: Expectativa Selic fim de ano (Focus — % a.a.)

        Args:
            series_code: Código da série no SGS.
            start_date: Data inicial (default: 5 anos atrás).
            end_date: Data final (default: hoje).

        Returns:
            DataFrame com colunas ['data', 'valor'].
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=5 * 365)

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

    def _fetch_series(self, name: str, period_days: int = 5 * 365) -> pd.DataFrame:
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
