"""Testes para o DDMFetcher — novos endpoints adicionados no Sprint 1.1.

Testes unitários usam mock do requests.get para isolar da rede.
Testes de integração (marcados com @pytest.mark.integration) fazem
chamadas reais à API e requerem DADOS_MERCADO_API_KEY no .env.
"""

from unittest.mock import MagicMock, patch

import pytest
from carteira_auto.data.fetchers.ddm_fetcher import DDMFetcher

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fetcher():
    """DDMFetcher com API key fake para testes unitários."""
    f = DDMFetcher()
    f._api_key = "fake-api-key-for-tests"
    return f


def _mock_response(data: list | dict, status_code: int = 200) -> MagicMock:
    """Cria mock de requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


# =============================================================================
# EMPRESAS — novos endpoints
# =============================================================================


class TestDDMFetcherEmpresas:
    """Testes para endpoints /empresas/ adicionados no Sprint 1.1."""

    def test_get_income_statement(self, fetcher):
        """get_income_statement retorna lista de DREs."""
        expected = [
            {
                "periodo": "2024-Q4",
                "receita_liquida": 150_000_000,
                "lucro_liquido": 25_000_000,
                "ebitda": 40_000_000,
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_income_statement("PETR4")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["lucro_liquido"] == 25_000_000
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert "empresas/resultados" in call_kwargs[0][0]
        assert call_kwargs[1]["params"]["ativo"] == "PETR4"

    def test_get_cash_flow(self, fetcher):
        """get_cash_flow retorna fluxo de caixa."""
        expected = [
            {
                "periodo": "2024-Q4",
                "fluxo_operacional": 18_000_000,
                "fluxo_investimento": -5_000_000,
                "fluxo_financiamento": -3_000_000,
                "free_cash_flow": 13_000_000,
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_cash_flow("VALE3")

        assert isinstance(result, list)
        assert result[0]["fluxo_operacional"] == 18_000_000
        call_kwargs = mock_get.call_args
        assert "fluxos-de-caixa" in call_kwargs[0][0]

    def test_get_shares(self, fetcher):
        """get_shares retorna número de ações."""
        expected = [
            {
                "data": "2024-12-31",
                "acoes_on": 1_000_000_000,
                "acoes_pn": 500_000_000,
                "total": 1_500_000_000,
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_shares("ITUB4")

        assert isinstance(result, list)
        assert result[0]["total"] == 1_500_000_000
        call_kwargs = mock_get.call_args
        assert "numero-de-acoes" in call_kwargs[0][0]

    def test_get_company_assets(self, fetcher):
        """get_company_assets retorna composição dos ativos."""
        expected = [
            {
                "periodo": "2024-Q4",
                "ativo_total": 500_000_000,
                "ativo_circulante": 120_000_000,
                "ativo_nao_circulante": 380_000_000,
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_company_assets("WEGE3")

        assert isinstance(result, list)
        assert result[0]["ativo_total"] == 500_000_000
        call_kwargs = mock_get.call_args
        assert "ativos-de-uma-empresa" in call_kwargs[0][0]

    def test_get_corporate_events_combina_splits_e_bonificacoes(self, fetcher):
        """get_corporate_events combina splits e bonificações."""
        splits = [{"data": "2023-06-01", "fator": 2.0}]
        bonuses = [{"data": "2022-04-01", "proporcao": 0.1}]

        with patch("requests.get") as mock_get:
            # Retorna splits na primeira chamada, bonuses na segunda
            mock_get.side_effect = [
                _mock_response(splits),
                _mock_response(bonuses),
            ]
            result = fetcher.get_corporate_events("BBAS3")

        assert len(result) == 2
        tipos = {e["tipo"] for e in result}
        assert "desdobramento" in tipos
        assert "bonificacao" in tipos

    def test_get_corporate_events_ticker_passado(self, fetcher):
        """get_corporate_events passa ticker correto para ambos endpoints."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            fetcher.get_corporate_events("ABEV3")

        assert mock_get.call_count == 2
        for call in mock_get.call_args_list:
            assert call[1]["params"]["ativo"] == "ABEV3"


# =============================================================================
# BOLSA — novos endpoints
# =============================================================================


class TestDDMFetcherBolsa:
    """Testes para endpoints /bolsa/ adicionados no Sprint 1.1."""

    def test_get_asset_list(self, fetcher):
        """get_asset_list retorna lista de ativos."""
        expected = [
            {
                "ticker": "PETR4",
                "nome": "Petrobras",
                "tipo": "acao",
                "cnpj": "33.000.167/0001-01",
            },
            {
                "ticker": "HGLG11",
                "nome": "CSHG Logística",
                "tipo": "fii",
                "cnpj": "11.260.094/0001-88",
            },
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_asset_list()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["ticker"] == "PETR4"
        call_kwargs = mock_get.call_args
        assert "lista-de-ativos" in call_kwargs[0][0]

    def test_get_asset_list_sem_params(self, fetcher):
        """get_asset_list não passa parâmetros extras."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            fetcher.get_asset_list()

        # Endpoint de listagem não deve ter params de ativo
        call_kwargs = mock_get.call_args
        assert call_kwargs[1].get("params") is None

    def test_get_index_details(self, fetcher):
        """get_index_details retorna composição do índice."""
        expected = {
            "codigo": "IBOV",
            "nome": "Ibovespa",
            "composicao": [{"ticker": "PETR4", "peso": 0.12}],
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_index_details("IBOV")

        assert isinstance(result, dict)
        assert result["codigo"] == "IBOV"
        call_kwargs = mock_get.call_args
        assert "detalhes-de-um-indice" in call_kwargs[0][0]
        assert call_kwargs[1]["params"]["indice"] == "IBOV"

    def test_get_foreign_investors(self, fetcher):
        """get_foreign_investors retorna fluxo estrangeiro."""
        expected = [
            {"data": "2025-01-15", "compras": 2_500_000_000, "vendas": 1_800_000_000}
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_foreign_investors()

        assert isinstance(result, list)
        assert result[0]["compras"] == 2_500_000_000
        call_kwargs = mock_get.call_args
        assert "investidores-estrangeiros" in call_kwargs[0][0]


# =============================================================================
# FUNDOS DE INVESTIMENTO
# =============================================================================


class TestDDMFetcherFundos:
    """Testes para endpoints /fundos-de-investimento/."""

    def test_get_fund_list(self, fetcher):
        """get_fund_list retorna lista de fundos."""
        expected = [
            {"nome": "Fundo XP Dividendos", "cnpj": "12.345.678/0001-90", "tipo": "FIA"}
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_fund_list()

        assert isinstance(result, list)
        assert result[0]["tipo"] == "FIA"
        call_kwargs = mock_get.call_args
        assert "lista-de-fundos" in call_kwargs[0][0]

    def test_get_fund_quotes(self, fetcher):
        """get_fund_quotes retorna histórico de cotas."""
        expected = [{"data": "2025-01-15", "cota": 15.82}]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_fund_quotes("12345678000190")

        assert isinstance(result, list)
        assert result[0]["cota"] == 15.82
        call_kwargs = mock_get.call_args
        assert "historico-de-cotacoes" in call_kwargs[0][0]
        assert call_kwargs[1]["params"]["fundo"] == "12345678000190"


# =============================================================================
# TÍTULOS PÚBLICOS — novos endpoints
# =============================================================================


class TestDDMFetcherTitulosPublicos:
    """Testes para endpoints /titulos-publicos/ adicionados no Sprint 1.1."""

    def test_get_all_treasury_list(self, fetcher):
        """get_all_treasury_list retorna lista completa de títulos."""
        expected = [
            {"codigo": "LFT-2029", "tipo": "LFT", "vencimento": "2029-03-01"},
            {"codigo": "NTN-B-2035", "tipo": "NTN-B", "vencimento": "2035-05-15"},
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_all_treasury_list()

        assert isinstance(result, list)
        assert len(result) == 2
        call_kwargs = mock_get.call_args
        assert "lista-de-titulos-publicos" in call_kwargs[0][0]

    def test_get_treasury_price_history_sem_filtro(self, fetcher):
        """get_treasury_price_history sem filtro retorna todos os títulos."""
        expected = [
            {
                "titulo": "LFT 2029",
                "data": "2025-01-15",
                "preco": 14_200.50,
                "taxa": 0.1225,
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_treasury_price_history()

        assert isinstance(result, list)
        call_kwargs = mock_get.call_args
        assert "historico-de-precos" in call_kwargs[0][0]
        # Sem filtro: params deve ser None
        assert call_kwargs[1]["params"] is None

    def test_get_treasury_price_history_com_filtro(self, fetcher):
        """get_treasury_price_history com título filtra corretamente."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            fetcher.get_treasury_price_history("LFT 2029")

        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["titulo"] == "LFT 2029"


# =============================================================================
# MACRO — novos endpoints
# =============================================================================


class TestDDMFetcherMacro:
    """Testes para endpoints /macro/ adicionados no Sprint 1.1."""

    def test_get_market_expectations(self, fetcher):
        """get_market_expectations retorna expectativas de mercado."""
        expected = [
            {
                "indicador": "SELIC",
                "horizonte": "2025-12",
                "mediana": 10.50,
                "media": 10.65,
            },
            {
                "indicador": "IPCA",
                "horizonte": "2025",
                "mediana": 4.20,
                "media": 4.35,
            },
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_market_expectations()

        assert isinstance(result, list)
        assert len(result) == 2
        indicadores = [e["indicador"] for e in result]
        assert "SELIC" in indicadores
        call_kwargs = mock_get.call_args
        assert "expectativas" in call_kwargs[0][0]


# =============================================================================
# MOEDAS — novos endpoints
# =============================================================================


class TestDDMFetcherMoedas:
    """Testes para endpoints /moedas/ adicionados no Sprint 1.1."""

    def test_get_currencies(self, fetcher):
        """get_currencies retorna lista de moedas."""
        expected = [
            {"codigo": "USD", "nome": "Dólar Americano"},
            {"codigo": "EUR", "nome": "Euro"},
            {"codigo": "BRL", "nome": "Real Brasileiro"},
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_currencies()

        assert isinstance(result, list)
        codigos = [m["codigo"] for m in result]
        assert "USD" in codigos
        assert "BRL" in codigos
        call_kwargs = mock_get.call_args
        assert "lista-de-moedas" in call_kwargs[0][0]


# =============================================================================
# NOTÍCIAS
# =============================================================================


class TestDDMFetcherNoticias:
    """Testes para endpoint /noticias/."""

    def test_get_news_sem_ticker(self, fetcher):
        """get_news sem ticker retorna notícias gerais."""
        expected = [
            {
                "titulo": "Ibovespa sobe 2%",
                "fonte": "Valor Econômico",
                "publicado_em": "2025-03-25T10:00:00",
                "resumo": "Bolsa brasileira...",
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response(expected)
            result = fetcher.get_news()

        assert isinstance(result, list)
        assert result[0]["fonte"] == "Valor Econômico"
        call_kwargs = mock_get.call_args
        assert "ultimas-noticias" in call_kwargs[0][0]
        # Sem ticker: params deve ser None
        assert call_kwargs[1]["params"] is None

    def test_get_news_com_ticker(self, fetcher):
        """get_news com ticker filtra por ativo."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            fetcher.get_news("PETR4")

        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["ativo"] == "PETR4"

    def test_get_news_retorna_lista(self, fetcher):
        """get_news sempre retorna lista mesmo sem resultados."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            result = fetcher.get_news("TICKERNAOEXISTE")

        assert isinstance(result, list)
        assert result == []


# =============================================================================
# ERROS E AUTENTICAÇÃO
# =============================================================================


class TestDDMFetcherErros:
    """Testes de tratamento de erros."""

    def test_token_invalido_raises_permission_error(self):
        """Token inválido levanta PermissionError."""
        fetcher = DDMFetcher()
        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.status_code = 401
            mock_get.return_value = mock
            with pytest.raises(PermissionError, match="token inválido"):
                fetcher._get("/empresas/resultados", params={"ativo": "PETR4"})

    def test_acesso_negado_raises_permission_error(self):
        """403 levanta PermissionError com mensagem de permissão."""
        fetcher = DDMFetcher()
        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.status_code = 403
            mock_get.return_value = mock
            with pytest.raises(PermissionError, match="acesso negado"):
                fetcher._get("/noticias/ultimas-noticias")

    def test_rate_limit_raises_runtime_error(self):
        """429 levanta RuntimeError de rate limit."""
        fetcher = DDMFetcher()
        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.status_code = 429
            mock_get.return_value = mock
            with pytest.raises(RuntimeError, match="rate limit"):
                fetcher._get("/macro/expectativas")


# =============================================================================
# TESTES DE INTEGRAÇÃO (requerem API key real)
# =============================================================================


@pytest.mark.integration
class TestDDMFetcherIntegration:
    """Testes de integração — requerem DADOS_MERCADO_API_KEY no .env.

    Execute com: pytest -m integration tests/unit/test_ddm_fetcher.py
    """

    def test_get_income_statement_real(self):
        """DRE real da Petrobras — verifica estrutura da resposta."""
        fetcher = DDMFetcher()
        if not fetcher._api_key:
            pytest.skip("DADOS_MERCADO_API_KEY não configurada")

        result = fetcher.get_income_statement("PETR4")
        assert isinstance(result, list)
        if result:
            assert any(k in result[0] for k in ["periodo", "receita", "lucro"])

    def test_get_asset_list_real(self):
        """Lista de ativos real — verifica se PETR4 está presente."""
        fetcher = DDMFetcher()
        if not fetcher._api_key:
            pytest.skip("DADOS_MERCADO_API_KEY não configurada")

        result = fetcher.get_asset_list()
        assert isinstance(result, list)
        assert len(result) > 100  # B3 tem centenas de ativos
        tickers = [a.get("ticker", a.get("ativo", "")) for a in result]
        assert any("PETR" in t for t in tickers)

    def test_get_market_expectations_real(self):
        """Expectativas de mercado reais — verifica SELIC/IPCA."""
        fetcher = DDMFetcher()
        if not fetcher._api_key:
            pytest.skip("DADOS_MERCADO_API_KEY não configurada")

        result = fetcher.get_market_expectations()
        assert isinstance(result, list)
        if result:
            indicadores = [e.get("indicador", "").upper() for e in result]
            assert any(i in indicadores for i in ["SELIC", "IPCA", "PIB"])

    def test_get_news_real(self):
        """Notícias reais — verifica estrutura."""
        fetcher = DDMFetcher()
        if not fetcher._api_key:
            pytest.skip("DADOS_MERCADO_API_KEY não configurada")

        result = fetcher.get_news()
        assert isinstance(result, list)
        if result:
            assert any(k in result[0] for k in ["titulo", "title", "headline"])

    def test_get_treasury_price_history_lft(self):
        """Histórico de preços LFT — verifica que retorna dados."""
        fetcher = DDMFetcher()
        if not fetcher._api_key:
            pytest.skip("DADOS_MERCADO_API_KEY não configurada")

        result = fetcher.get_treasury_price_history("LFT")
        assert isinstance(result, list)
