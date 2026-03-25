"""Fetcher do Dados de Mercado (DDM) — API REST.

API: https://api.dadosdemercado.com.br/v1
Docs: https://www.dadosdemercado.com.br/api/docs
Auth: Bearer token via header Authorization.
Formato: JSON.

Endpoints principais:
    - /empresas/*: dados de empresas (balanços, DRE, fluxo de caixa, indicadores)
    - /bolsa/*: cotações, índices, risco, investidores estrangeiros
    - /fiis/*: FIIs e dividendos
    - /fundos-de-investimento/*: fundos de investimento
    - /titulos-publicos/*: Tesouro Direto (preços, histórico)
    - /macro/*: índices econômicos, Focus, expectativas, curvas de juros
    - /moedas/*: câmbio, lista de moedas
    - /noticias/*: últimas notícias por ativo
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

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_income_statement(self, ticker: str) -> list[dict]:
        """Demonstrativo de Resultados (DRE) de uma empresa.

        Retorna série histórica de receita, lucro bruto, EBITDA, lucro líquido
        e demais linhas do DRE.

        Args:
            ticker: Código do ativo (ex: "PETR4").

        Returns:
            Lista de demonstrativos de resultado por período.
        """
        return self._get("/empresas/resultados", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_cash_flow(self, ticker: str) -> list[dict]:
        """Fluxo de caixa de uma empresa.

        Retorna fluxo operacional, de investimento e de financiamento.
        Útil para calcular FCF (Free Cash Flow) e qualidade de caixa.

        Args:
            ticker: Código do ativo (ex: "VALE3").

        Returns:
            Lista de fluxos de caixa por período.
        """
        return self._get("/empresas/fluxos-de-caixa", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_shares(self, ticker: str) -> list[dict]:
        """Número de ações de uma empresa.

        Retorna quantidade de ações ordinárias, preferenciais e total,
        incluindo ações em tesouraria.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com histórico do número de ações.
        """
        return self._get("/empresas/numero-de-acoes", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_company_assets(self, ticker: str) -> list[dict]:
        """Ativos de uma empresa (composição do ativo total).

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com composição dos ativos por período.
        """
        return self._get("/empresas/ativos-de-uma-empresa", params={"ativo": ticker})

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_corporate_events(self, ticker: str) -> list[dict]:
        """Eventos corporativos (desdobramentos e bonificações).

        Retorna histórico de splits, inplits e bonificações para
        ajuste de preços históricos.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista de eventos corporativos.
        """
        splits = self._get("/empresas/desdobramentos", params={"ativo": ticker})
        bonuses = self._get("/empresas/bonificacoes", params={"ativo": ticker})
        # Combina e marca tipo
        for e in splits:
            e.setdefault("tipo", "desdobramento")
        for e in bonuses:
            e.setdefault("tipo", "bonificacao")
        return splits + bonuses

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

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_asset_list(self) -> list[dict]:
        """Lista completa de ativos negociados na B3.

        Retorna todos os ativos disponíveis com metadados (ticker, nome, tipo,
        CNPJ quando disponível). Usado para mapeamento ticker→CNPJ.

        Returns:
            Lista de ativos com metadados.
        """
        return self._get("/bolsa/lista-de-ativos")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_index_details(self, index: str) -> dict:
        """Detalhes de um índice (composição, setor, retornos).

        Args:
            index: Código do índice (ex: "IBOV", "IFIX", "SMLL").

        Returns:
            Dict com detalhes e composição do índice.
        """
        return self._get("/bolsa/detalhes-de-um-indice", params={"indice": index})

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_foreign_investors(self) -> list[dict]:
        """Fluxo de investidores estrangeiros na B3.

        Retorna dados de compra/venda de estrangeiros — útil como
        indicador de sentimento institucional.

        Returns:
            Lista com histórico de fluxo estrangeiro.
        """
        return self._get("/bolsa/investidores-estrangeiros")

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

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_fund_list(self) -> list[dict]:
        """Lista de fundos de investimento disponíveis.

        Returns:
            Lista de fundos com metadados (nome, CNPJ, tipo).
        """
        return self._get("/fundos-de-investimento/lista-de-fundos")

    @log_execution
    @cache_result(ttl_seconds=900)
    def get_fund_quotes(self, fund_id: str) -> list[dict]:
        """Histórico de cotas de um fundo de investimento.

        Args:
            fund_id: Identificador do fundo (CNPJ ou código DDM).

        Returns:
            Lista de cotas históricas.
        """
        return self._get(
            "/fundos-de-investimento/historico-de-cotacoes", params={"fundo": fund_id}
        )

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

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_all_treasury_list(self) -> list[dict]:
        """Lista completa de todos os títulos públicos disponíveis.

        Inclui títulos não disponíveis no Tesouro Direto (ex: emissões antigas).

        Returns:
            Lista de títulos públicos com metadados.
        """
        return self._get("/titulos-publicos/lista-de-titulos-publicos")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_treasury_price_history(self, title: str | None = None) -> list[dict]:
        """Histórico de preços de títulos públicos.

        Fundamental para construir a curva de juros histórica e avaliar
        LFTs, NTN-Bs e LTNs ao longo do tempo.

        Args:
            title: Nome/código do título (ex: "LFT 2029", "NTN-B 2035").
                   Se None, retorna todos os títulos.

        Returns:
            Lista com histórico de preços e taxas.
        """
        params = {}
        if title:
            params["titulo"] = title
        return self._get("/titulos-publicos/historico-de-precos", params=params or None)

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

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_market_expectations(self) -> list[dict]:
        """Expectativas do mercado para indicadores macroeconômicos.

        Retorna o consenso de mercado (mediana, média, desvio) para
        SELIC, IPCA, PIB, câmbio e outros indicadores com horizonte
        de até 5 anos. Complementa o Boletim Focus.

        Returns:
            Lista de expectativas por indicador e horizonte temporal.
        """
        return self._get("/macro/expectativas")

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

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_currencies(self) -> list[dict]:
        """Lista de moedas disponíveis para conversão.

        Returns:
            Lista de moedas com código e nome.
        """
        return self._get("/moedas/lista-de-moedas")

    # ============================================================================
    # NOTÍCIAS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_news(self, ticker: str | None = None) -> list[dict]:
        """Últimas notícias do mercado, opcionalmente filtradas por ativo.

        Principal fonte de dados para análise de sentimento (Fase 5 NLP).
        Retorna títulos, resumos, fontes e timestamps.

        Args:
            ticker: Código do ativo para filtrar notícias (ex: "PETR4").
                    Se None, retorna notícias gerais de mercado.

        Returns:
            Lista de artigos com título, resumo, fonte e data.
        """
        params = {}
        if ticker:
            params["ativo"] = ticker
        return self._get("/noticias/ultimas-noticias", params=params or None)

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
