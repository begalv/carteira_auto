"""Fetcher do Dados de Mercado (DDM) — API REST.

API: https://api.dadosdemercado.com.br/v1
Docs: https://www.dadosdemercado.com.br/api/docs
Auth: Bearer token via header Authorization.
Formato: JSON.

Endpoints (estrutura REST v1 — migração 2025):
    - /v1/companies/{ticker}/*: balanços, DRE, fluxo de caixa, indicadores
    - /v1/tickers/{ticker}/*: cotações, DY, risco
    - /v1/indexes/{index}: índices de mercado
    - /v1/reits/{ticker}/*: FIIs e dividendos
    - /v1/funds/{id}/*: fundos de investimento
    - /v1/treasury/{isin}: Tesouro Direto (histórico de preços)
    - /v1/bonds/{isin}: títulos públicos (histórico)
    - /v1/macro/{indicador}: séries macro (SELIC, IPCA, CDI, IGP-M)
    - /v1/macro/focus/{indicador}: expectativas Focus
    - /v1/macro/yield_curves/{curva}: curvas de juros
    - /v1/currencies/{de}/{para}/{data}: câmbio histórico
    - /v1/news: notícias (filtro opcional por ticker)
    - /v1/investors: fluxo de estrangeiros

Identificadores de empresa:
    - ticker completo (ex: "WEGE3") como path param em /companies/{ticker}/*
    - ISIN como path param em /treasury/{isin} e /bonds/{isin}
"""

from __future__ import annotations

from datetime import date

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

    Uso:
        ddm = DDMFetcher()

        # Dados de empresas
        companies = ddm.get_companies()
        balances  = ddm.get_balance_sheet("WEGE3")
        incomes   = ddm.get_income_statement("PETR4")

        # Mercado
        quotes = ddm.get_quotations("VALE3")
        fiis   = ddm.get_fii_list()

        # Macro
        selic    = ddm.get_macro_series("selic")
        focus    = ddm.get_focus_bulletin("selic")
        curvas   = ddm.get_interest_curves()

        # Câmbio
        fx = ddm.get_currency_conversion("USD", "BRL")
    """

    def __init__(self) -> None:
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
    # EMPRESAS — /v1/companies/{ticker}/
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_companies(self) -> list[dict]:
        """Lista de todas as companhias abertas cadastradas na DDM.

        Returns:
            Lista com campos: name, b3_issuer_code, cvm_code, cnpj,
            b3_sector, b3_segment, founding_date, website, etc.
        """
        return self._get("/companies")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_stock_data(self, ticker: str) -> list[dict]:
        """Indicadores de mercado históricos de uma empresa (P/L, EV/EBITDA, etc.).

        Args:
            ticker: Código do ativo (ex: "PETR4", "WEGE3").

        Returns:
            Lista com indicadores de mercado por período.
        """
        return self._get(f"/companies/{ticker}/market_ratios")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_financials(self, ticker: str) -> list[dict]:
        """Indicadores financeiros históricos de uma empresa (ROE, ROA, margens).

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com indicadores financeiros por período.
        """
        return self._get(f"/companies/{ticker}/ratios")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_dividends(self, ticker: str) -> list[dict]:
        """Histórico de dividendos e JCP de uma empresa.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com campos: amount, adj_amount, approval_date, ex_date,
            payment_date, type (dividendo/jcp).
        """
        return self._get(f"/companies/{ticker}/dividends")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_balance_sheet(self, ticker: str) -> list[dict]:
        """Balanço patrimonial histórico de uma empresa.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com ativos, passivos e PL por período.
        """
        return self._get(f"/companies/{ticker}/balances")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_income_statement(self, ticker: str) -> list[dict]:
        """Demonstrativo de Resultados (DRE) histórico de uma empresa.

        Args:
            ticker: Código do ativo (ex: "PETR4").

        Returns:
            Lista com receita, lucro bruto, EBITDA, lucro líquido por período.
        """
        return self._get(f"/companies/{ticker}/incomes")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_cash_flow(self, ticker: str) -> list[dict]:
        """Fluxo de caixa histórico de uma empresa.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com fluxo operacional, de investimento e financiamento.
        """
        return self._get(f"/companies/{ticker}/cash_flows")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_shares(self, ticker: str) -> list[dict]:
        """Número de ações de uma empresa.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com ações ordinárias, preferenciais e total.
        """
        return self._get(f"/companies/{ticker}/shares")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_company_assets(self, ticker: str) -> list[dict]:
        """Composição dos ativos de uma empresa por período.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com composição do ativo total por período.
        """
        return self._get(f"/companies/{ticker}/balances")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_corporate_events(self, ticker: str) -> list[dict]:
        """Eventos corporativos: desdobramentos e bonificações.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista de splits com tipo marcado ("split").
        """
        splits = self._get(f"/companies/{ticker}/splits")
        for e in splits:
            e.setdefault("tipo", "split")
        return splits

    # ============================================================================
    # TICKERS / BOLSA — /v1/tickers/{ticker}/
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=900)
    def get_quotations(
        self, ticker: str, period_init: str | None = None, period_end: str | None = None
    ) -> list[dict]:
        """Cotações históricas OHLCV de um ativo.

        Args:
            ticker: Código do ativo (ex: "PETR4", "WEGE3").
            period_init: Data início "YYYY-MM-DD" (opcional).
            period_end: Data fim "YYYY-MM-DD" (opcional).

        Returns:
            Lista com campos: date, open, close, max, min, adj_close.
        """
        params: dict = {}
        if period_init:
            params["period_init"] = period_init
        if period_end:
            params["period_end"] = period_end
        return self._get(f"/tickers/{ticker}/quotes", params=params or None)

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_market_indices(self) -> list[dict]:
        """Lista de índices de mercado (IBOV, IFIX, SMLL, etc.).

        Returns:
            Lista com campos: ticker, name, market, last_quote, change.
        """
        return self._get("/indexes")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_risk_indicators(
        self,
        ticker: str,
        index: str = "IBOV",
        period_init: str | None = None,
        period_end: str | None = None,
    ) -> list[dict]:
        """Indicadores de risco de um ativo em relação a um índice (beta, alpha, etc.).

        Args:
            ticker: Código do ativo.
            index: Índice de referência (padrão: "IBOV").
            period_init: Data início "YYYY-MM-DD" (opcional).
            period_end: Data fim "YYYY-MM-DD" (opcional).

        Returns:
            Lista com métricas de risco por período.
        """
        params: dict = {}
        if period_init:
            params["period_init"] = period_init
        if period_end:
            params["period_end"] = period_end
        return self._get(
            f"/tickers/{ticker}/risk_measures/{index}",
            params=params or None,
        )

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_dividend_yield(self, ticker: str) -> list[dict]:
        """Dividend yield histórico anual de um ativo.

        Args:
            ticker: Código do ativo.

        Returns:
            Lista com campos: year, amount, close, dy (yield anual).
        """
        return self._get(f"/tickers/{ticker}/dy")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_asset_list(self) -> list[dict]:
        """Lista completa de ativos negociados na B3.

        Returns:
            Lista com campos: ticker, name, type, currency, isin,
            issuer_code, last_quote, market.
        """
        return self._get("/tickers")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_index_details(self, index: str) -> list[dict]:
        """Composição e histórico de um índice (IBOV, IFIX, etc.).

        Args:
            index: Código do índice (ex: "IBOV", "IFIX", "SMLL").

        Returns:
            Lista com participações por ativo e histórico de valor.
        """
        return self._get(f"/indexes/{index}")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_foreign_investors(self) -> list[dict]:
        """Fluxo histórico de investidores estrangeiros na B3.

        Returns:
            Lista com campos: date, companies (compras/vendas), saldo.
        """
        return self._get("/investors")

    # ============================================================================
    # FIIs — /v1/reits/
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_fii_list(self) -> list[dict]:
        """Lista de Fundos de Investimento Imobiliário (FIIs).

        Returns:
            Lista com campos: ticker, name, b3_sector, about, etc.
        """
        return self._get("/reits")

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_fii_dividends(
        self, ticker: str, date_from: str | None = None
    ) -> list[dict]:
        """Dividendos históricos de um FII.

        Args:
            ticker: Código do FII (ex: "HGLG11", "KNCA11").
            date_from: Data início "YYYY-MM-DD" (opcional).

        Returns:
            Lista com campos: amount, ex_date, payment_date.
        """
        params = {"date_from": date_from} if date_from else None
        return self._get(f"/reits/{ticker}/dividends", params=params)

    # ============================================================================
    # FUNDOS — /v1/funds/
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_fund_list(self) -> list[dict]:
        """Lista de fundos de investimento.

        Returns:
            Lista com campos: cnpj, name, fund_class, benchmark, begin_date.
        """
        return self._get("/funds")

    @log_execution
    @cache_result(ttl_seconds=900)
    def get_fund_quotes(self, fund_id: str) -> list[dict]:
        """Histórico de cotas de um fundo de investimento.

        Args:
            fund_id: CNPJ ou ID DDM do fundo
                     (obter de get_fund_list() → cnpj).

        Returns:
            Lista com campos: date, quota_value, net_worth.
        """
        return self._get(f"/funds/{fund_id}/quotes")

    # ============================================================================
    # TÍTULOS PÚBLICOS — /v1/treasury/ e /v1/bonds/
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_treasury_list(self) -> list[dict]:
        """Títulos do Tesouro Direto disponíveis para compra.

        Returns:
            Lista com campos: name, isin, index, due_date, pu,
            min_investment, buy_rate.
        """
        return self._get("/treasury")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_treasury_prices(self) -> list[dict]:
        """Preços atuais dos títulos do Tesouro Direto.

        Alias de get_treasury_list() — mesmo endpoint, retorna PU e taxas.
        """
        return self._get("/treasury")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_all_treasury_list(self) -> list[dict]:
        """Lista completa de todos os títulos públicos (incluindo vencidos).

        Returns:
            Lista com campos: isin, index, maturity_date, issuance_date,
            coupon_frequency.
        """
        return self._get("/bonds")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_treasury_price_history(self, isin: str | None = None) -> list[dict]:
        """Histórico de preços de um título público.

        Args:
            isin: Código ISIN do título (ex: "BRSTNCNTB3E2" para NTN-B 2035).
                  Use get_treasury_list() para obter o ISIN.
                  Se None, retorna lista geral (get_all_treasury_list).

        Returns:
            Lista com campos: date, buy_rate, buy_value, sell_rate, sell_value.
        """
        if isin:
            return self._get(f"/treasury/{isin}")
        return self._get("/bonds")

    # ============================================================================
    # MACRO — /v1/macro/
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_macro_series(self, indicator: str) -> list[dict]:
        """Série histórica de um indicador macroeconômico.

        Args:
            indicator: Nome do indicador. Opções confirmadas:
                "selic" — taxa Selic diária
                "cdi"   — CDI diário
                "ipca"  — IPCA mensal
                "igp-m" — IGP-M mensal

        Returns:
            Lista com campos: date, value, code, slug.
        """
        return self._get(f"/macro/{indicator}")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_economic_indices(self) -> dict[str, list[dict]]:
        """Principais indicadores econômicos brasileiros.

        Retorna dicionário com séries de SELIC, CDI, IPCA e IGP-M.

        Returns:
            Dict {"selic": [...], "cdi": [...], "ipca": [...], "igp-m": [...]}.
        """
        result: dict[str, list[dict]] = {}
        for indicator in ["selic", "cdi", "ipca", "igp-m"]:
            try:
                result[indicator] = self._get(f"/macro/{indicator}")
            except Exception as e:
                logger.warning(f"DDM: falha ao buscar macro/{indicator}: {e}")
                result[indicator] = []
        return result

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_bulletin(self, indicator: str = "selic") -> list[dict]:
        """Boletim Focus — expectativas do mercado para um indicador.

        Args:
            indicator: Indicador do Focus. Opções: "selic", "ipca".
                       Padrão: "selic".

        Returns:
            Lista com campos: date, index, last, last_week, last_month,
            answers (mediana, média, desvio).
        """
        return self._get(f"/macro/focus/{indicator}")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_interest_curves(self, curve: str = "ettj_ipca") -> list[dict]:
        """Curva de juros (estrutura a termo).

        Args:
            curve: Identificador da curva. Padrão: "ettj_ipca"
                   (curva real IPCA+). Outras curvas disponíveis
                   via /v1/postman.

        Returns:
            Lista com campos: date, vertex, value, curve.
        """
        return self._get(f"/macro/yield_curves/{curve}")

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_market_expectations(self) -> list[dict]:
        """Expectativas do mercado para o IPCA (Boletim Focus IPCA).

        Returns:
            Lista com expectativas por horizonte temporal.
        """
        return self._get("/macro/focus/ipca")

    # ============================================================================
    # MOEDAS — /v1/currencies/
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_currencies(self) -> list[dict]:
        """Lista de moedas disponíveis para conversão.

        Returns:
            Lista com campos: symbol, name (ex: USD, BRL, EUR).
        """
        return self._get("/currencies")

    @log_execution
    @cache_result(ttl_seconds=900)
    def get_currency_conversion(
        self,
        from_currency: str = "USD",
        to_currency: str = "BRL",
        reference_date: str | None = None,
    ) -> dict:
        """Taxa de câmbio para uma data específica.

        Args:
            from_currency: Moeda de origem (ex: "USD").
            to_currency: Moeda de destino (ex: "BRL").
            reference_date: Data "YYYY-MM-DD". Padrão: data de hoje.

        Returns:
            Dict com campos: currency_from, currency_to, date, value.
        """
        from datetime import timedelta

        if reference_date:
            dt = reference_date
        else:
            # API pode ter lag de 1 dia — tenta hoje, fallback para ontem
            today = date.today()
            try:
                return self._get(
                    f"/currencies/{from_currency}/{to_currency}/{today.isoformat()}"
                )
            except Exception:
                dt = (today - timedelta(days=1)).isoformat()
        return self._get(f"/currencies/{from_currency}/{to_currency}/{dt}")

    # ============================================================================
    # NOTÍCIAS — /v1/news
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=1800)
    def get_news(self, ticker: str | None = None) -> list[dict]:
        """Últimas 100 notícias do mercado.

        Args:
            ticker: Código do ativo para filtrar (ex: "PETR4").
                    Se None, retorna notícias gerais.

        Returns:
            Lista com campos: title, category, source, published_at, url.
        """
        params = {"ticker": ticker} if ticker else None
        return self._get("/news", params=params)

    # ============================================================================
    # INTERNOS
    # ============================================================================

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=60)
    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Faz GET request à API DDM.

        Args:
            endpoint: Caminho do endpoint (ex: "/companies/WEGE3/balances").
            params: Query parameters opcionais.

        Returns:
            Resposta JSON (dict ou list).

        Raises:
            PermissionError: Erro de autenticação (401/403).
            RuntimeError: Rate limit excedido (429).
            requests.HTTPError: Outros erros HTTP.
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
