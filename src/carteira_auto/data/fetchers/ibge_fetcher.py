"""Fetcher do IBGE — API SIDRA (Sistema IBGE de Recuperação Automática).

Tabelas utilizadas:

    Inflação:
        - 1737: IPCA — variação mensal (%) | Mensal (~9 dias após fim do mês)
        - 7060: IPCA por grupos — variação mensal (%) | Mensal

    Atividade econômica:
        - 5932: PIB trimestral — variação % vs mesmo trimestre do ano anterior | Trimestral
        - 6381: PNAD — taxa de desocupação (%) | Trimestral móvel (divulgação trimestral)

API: https://apisidra.ibge.gov.br/values/t/{tabela}/...
Formato: JSON (default)
Sem autenticação. Limite: 100.000 valores por consulta.

Estrutura da URL:
    /t/{tabela}           — tabela
    /p/last {n}           — últimos n períodos (mês, trimestre etc. conforme tabela)
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
        """IPCA — variação mensal (%) | Mensal (~9 dias após fim do mês) | Tabela 1737.

        Args:
            months: Número de meses a buscar (cada período = 1 mês).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = variação % mensal (ex: 0.52 = 0,52%).
            Para acumulado anual: ((1 + valor/100).prod() - 1) * 100
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
        """IPCA por grupos de produtos — variação mensal (%) | Mensal | Tabela 7060.

        Desagregação por grupos: Alimentação, Habitação, Transportes, Saúde,
        Comunicação, Despesas pessoais, Vestuário, Educação.

        Args:
            months: Número de meses a buscar (cada período = 1 mês).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel', 'grupo'].
            valor = variação % mensal por grupo.
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
        """PIB trimestral — variação % vs mesmo trimestre do ano anterior | Trimestral | Tabela 5932.

        Args:
            quarters: Número de trimestres a buscar (cada período = 1 trimestre).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = variação % em relação ao mesmo trimestre do ano anterior.
            Exemplo: 2.3 = PIB cresceu 2,3% vs mesmo trimestre do ano anterior.
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
    def get_unemployment(self, quarters: int = 8) -> pd.DataFrame:
        """Taxa de desocupação — PNAD Contínua (%) | Trimestral | Tabela 6381.

        Cada período = 1 trimestre móvel (ex: jan-fev-mar, fev-mar-abr...).
        Reflete a média da taxa no trimestre, não um mês específico.

        Args:
            quarters: Número de trimestres a buscar (cada período = 1 trimestre móvel).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = taxa de desocupação % (ex: 8.2 = 8,2% da força de trabalho).
        """
        path = (
            f"/t/{self._tables['pnad_desocupacao']}"
            f"/p/last {quarters}"
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
