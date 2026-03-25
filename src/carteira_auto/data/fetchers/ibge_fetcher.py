"""Fetcher do IBGE — API SIDRA (Sistema IBGE de Recuperação Automática).

Tabelas utilizadas:
    - 1737: IPCA — variação mensal (%)
    - 7060: IPCA por grupos de produtos
    - 5932: PIB trimestral — taxa de variação (%)
    - 6381: PNAD — taxa de desocupação (%)

API: https://apisidra.ibge.gov.br/values/t/{tabela}/...
Formato: JSON (default)
Sem autenticação. Limite: 100.000 valores por consulta.

Estrutura da URL:
    /t/{tabela}           — tabela
    /p/last {n}           — últimos n períodos
    /v/{variáveis}        — variáveis (allxp = todas exceto %)
    /n1/1                 — nível Brasil
    /c{classificação}/all — todas as categorias
"""

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


class IBGEFetcher:
    """Fetcher para dados do IBGE via API SIDRA."""

    def __init__(self):
        self._base_url = settings.ibge.BASE_URL
        self._timeout = settings.ibge.TIMEOUT
        self._tables = constants.IBGE_TABLE_IDS

    # ============================================================================
    # MÉTODOS PÚBLICOS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca(self, months: int = 12) -> pd.DataFrame:
        """IPCA — variação mensal (%).

        Tabela 1737, variável 63 (variação mensal).
        Nível Brasil (n1/1).

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
        """
        path = (
            f"/t/{self._tables['ipca']}"
            f"/p/last {months}"
            "/v/63"  # Variação mensal
            "/n1/1"  # Brasil
            "/f/c"  # Apenas códigos
        )
        return self._fetch(path)

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca_detailed(self, months: int = 12) -> pd.DataFrame:
        """IPCA por grupos de produtos.

        Tabela 7060, variável 63 (variação mensal).
        Todas as categorias da classificação 315 (grupos).

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel', 'grupo'].
        """
        path = (
            f"/t/{self._tables['ipca_grupos']}"
            f"/p/last {months}"
            "/v/63"  # Variação mensal
            "/n1/1"  # Brasil
            "/c315/allxt"  # Grupos — sem total
            "/f/n"  # Nomes
        )
        return self._fetch(path)

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_pib(self, quarters: int = 8) -> pd.DataFrame:
        """PIB trimestral — taxa de variação (%).

        Tabela 5932, variável 6561 (taxa de variação % contra trimestre anterior).
        Nível Brasil (n1/1).

        Args:
            quarters: Número de trimestres a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
        """
        path = (
            f"/t/{self._tables['pib_trimestral']}"
            f"/p/last {quarters}"
            "/v/6561"  # Taxa de variação % em relação ao mesmo período do ano anterior
            "/n1/1"  # Brasil
            "/c11255/90707"  # Setor = PIB total (evita dados ".." da classificação setorial)
        )
        return self._fetch(path)

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_unemployment(self, months: int = 12) -> pd.DataFrame:
        """Taxa de desocupação — PNAD Contínua (%).

        Tabela 6381, variável 4099 (taxa de desocupação).
        Nível Brasil (n1/1).

        Args:
            months: Número de trimestres móveis a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
        """
        path = (
            f"/t/{self._tables['pnad_desocupacao']}"
            f"/p/last {months}"
            "/v/4099"  # Taxa de desocupação
            "/n1/1"  # Brasil
            "/f/c"
        )
        return self._fetch(path)

    # ============================================================================
    # INTERNOS
    # ============================================================================

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch(self, path: str) -> pd.DataFrame:
        """Faz a requisição ao SIDRA e retorna DataFrame normalizado.

        Args:
            path: Caminho da URL após o base URL.

        Returns:
            DataFrame com colunas normalizadas.
        """
        url = f"{self._base_url}{path}"
        logger.debug(f"IBGE SIDRA: {url}")

        response = requests.get(
            url,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

        data = response.json()

        if not data or len(data) <= 1:
            # Primeira linha é header
            logger.warning(f"SIDRA: sem dados para {path}")
            return pd.DataFrame(columns=["periodo", "valor", "variavel"])

        # Remove header (primeira linha)
        rows = data[1:]

        # Normaliza para DataFrame
        df = pd.DataFrame(rows)

        # Mapeia colunas conhecidas
        result = pd.DataFrame()

        # Estrutura SIDRA: D1=período (mês/trimestre), D2=variável, D3+=localidade/classificações
        # Exemplo IPCA: D1C="202512" (mês), D1N="dezembro 2025", D2C="63", D2N="IPCA - Var. mensal"
        if "V" in df.columns:
            result["valor"] = pd.to_numeric(df["V"], errors="coerce")

        # Período — D1C (código) e D1N (nome legível)
        if "D1C" in df.columns:
            result["periodo_codigo"] = df["D1C"]
        if "D1N" in df.columns:
            result["periodo"] = df["D1N"]
        elif "D1C" in df.columns:
            result["periodo"] = df["D1C"]

        # Variável — D2N (nome descritivo)
        if "D2N" in df.columns:
            result["variavel"] = df["D2N"]

        # Classificações adicionais (grupos IPCA, etc.)
        for col in df.columns:
            if col.startswith("D3") or col.startswith("D4"):
                suffix = "N" if col.endswith("N") else "C"
                if suffix == "N":
                    result["grupo"] = df[col]

        # Unidade
        if "MN" in df.columns:
            result["unidade"] = df["MN"]

        # Remove linhas sem valor
        result = result.dropna(subset=["valor"])

        logger.debug(f"SIDRA: {len(result)} registros retornados")
        return result
