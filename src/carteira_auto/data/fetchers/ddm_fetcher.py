"""Fetcher do Dados de Mercado (DDM) — API REST.

API: https://api.dadosdemercado.com.br/v1
Docs: https://www.dadosdemercado.com.br/api/docs
Auth: Bearer token via header Authorization.
Formato: JSON.

Endpoints principais:
    - /empresas/*: dados de empresas (balanços, dividendos, indicadores)
    - /bolsa/*: cotações, índices, risco
    - /fiis/*: FIIs e dividendos
    - /titulos-publicos/*: Tesouro Direto
    - /macro/*: índices econômicos, Focus, curvas de juros
    - /moedas/*: câmbio
"""

import requests

from carteira_auto.config import settings
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
    rate_limit,
    retry,
)

logger = get_logger(__name__)


class DDMFetcher:
    """Fetcher para dados do Dados de Mercado (DDM).

    Requer API key configurada em settings.API_KEYS["ddm"].
    """

    def __init__(self):
        self._base_url = settings.ddm.BASE_URL
        self._timeout = settings.ddm.TIMEOUT
        self._api_key = settings.API_KEYS.get("ddm")

        if not self._api_key:
            logger.warning(
                "DDM API key não configurada. " "Defina DADOS_MERCADO_API_KEY no .env"
            )

    @property
    def _headers(self) -> dict[str, str]:
        """Headers de autenticação."""
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    # ============================================================================
    # EMPRESAS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_companies(self) -> list[dict]:
        """Lista de empresas disponíveis."""
        return self._get("/empresas/lista-de-empresas")

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_stock_data(self, ticker: str) -> dict:
        """Dados completos de uma ação (indicadores de mercado).

        Args:
            ticker: Código do ativo (ex: "PETR4").

        Returns:
            Dict com indicadores de mercado.
        """
        return self._get("/empresas/indicadores-de-mercado", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_financials(self, ticker: str) -> dict:
        """Indicadores financeiros de uma empresa.

        Args:
            ticker: Código do ativo.

        Returns:
            Dict com indicadores financeiros.
        """
        return self._get("/empresas/indicadores-financeiros", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_dividends(self, ticker: str) -> list[dict]:
        """Dividendos de uma empresa.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista de dividendos.
        """
        return self._get("/empresas/dividendos", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_balance_sheet(self, ticker: str) -> list[dict]:
        """Balanços de uma empresa.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista de balanços.
        """
        return self._get("/empresas/balancos", params={"ativo": ticker})

    # ============================================================================
    # BOLSA
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=900)
    def get_quotations(self, ticker: str) -> list[dict]:
        """Cotações históricas de um ativo.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista de cotações.
        """
        return self._get("/bolsa/cotacoes", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_market_indices(self) -> list[dict]:
        """Índices de mercado (IBOV, IFIX, etc.)."""
        return self._get("/bolsa/indices-de-mercado")

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_risk_indicators(self) -> list[dict]:
        """Indicadores de risco (EMBI+, CDS, etc.)."""
        return self._get("/bolsa/indicadores-de-risco")

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_dividend_yield(self, ticker: str) -> dict:
        """Rendimento de dividendos de um ativo."""
        return self._get("/bolsa/rendimento-de-dividendos", params={"ativo": ticker})

    # ============================================================================
    # FIIs
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_fii_list(self) -> list[dict]:
        """Lista de FIIs disponíveis."""
        return self._get("/fiis/lista-de-fiis")

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_fii_dividends(self, ticker: str) -> list[dict]:
        """Dividendos de um FII.

        Args:
            ticker: Código do FII (ex: "HGLG11").

        Returns:
            Lista de dividendos.
        """
        return self._get("/fiis/dividendos", params={"ativo": ticker})

    # ============================================================================
    # TÍTULOS PÚBLICOS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_treasury_list(self) -> list[dict]:
        """Lista de títulos do Tesouro Direto."""
        return self._get("/titulos-publicos/tesouro-direto")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_treasury_prices(self) -> list[dict]:
        """Preços atuais do Tesouro Direto."""
        return self._get("/titulos-publicos/precos-do-tesouro-direto")

    # ============================================================================
    # MACRO
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_economic_indices(self) -> list[dict]:
        """Índices econômicos (SELIC, IPCA, CDI, etc.)."""
        return self._get("/macro/indices-economicos")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_bulletin(self) -> list[dict]:
        """Boletim Focus (expectativas do mercado)."""
        return self._get("/macro/boletim-focus")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_interest_curves(self) -> list[dict]:
        """Curvas de juros."""
        return self._get("/macro/curvas-de-juros")

    # ============================================================================
    # MOEDAS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=900)
    def get_currency_conversion(
        self, from_currency: str = "USD", to_currency: str = "BRL"
    ) -> dict:
        """Conversão de moeda.

        Args:
            from_currency: Moeda de origem.
            to_currency: Moeda de destino.

        Returns:
            Dict com taxa de conversão.
        """
        return self._get(
            "/moedas/conversao",
            params={"de": from_currency, "para": to_currency},
        )

    # ============================================================================
    # INTERNOS
    # ============================================================================

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=60)
    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Faz GET request à API DDM.

        Args:
            endpoint: Caminho do endpoint (ex: "/empresas/dividendos").
            params: Query parameters.

        Returns:
            Resposta JSON (dict ou list).

        Raises:
            requests.HTTPError: Erro HTTP (401, 403, 429, etc.).
        """
        url = f"{self._base_url}{endpoint}"
        logger.debug(f"DDM: GET {endpoint} params={params}")

        response = requests.get(
            url,
            params=params,
            headers=self._headers,
            timeout=self._timeout,
        )

        if response.status_code == 401:
            raise PermissionError(
                "DDM API: token inválido ou ausente. "
                "Verifique DADOS_MERCADO_API_KEY no .env"
            )
        if response.status_code == 403:
            raise PermissionError(
                f"DDM API: acesso negado ao endpoint {endpoint}. "
                "Verifique permissões do token."
            )
        if response.status_code == 429:
            raise RuntimeError("DDM API: rate limit excedido")

        response.raise_for_status()

        data = response.json()
        logger.debug(f"DDM: {endpoint} retornou {type(data).__name__}")
        return data
