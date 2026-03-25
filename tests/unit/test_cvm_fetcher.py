"""Testes para CVMFetcher — dados abertos da CVM.

Cobertura:
    - Unit: mocks de requests.get e zipfile.ZipFile (sem rede)
    - Integration: @pytest.mark.integration (requer conectividade com dados.cvm.gov.br)
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from carteira_auto.data.fetchers.cvm_fetcher import CVMFetcher

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fetcher():
    """CVMFetcher pronto para uso."""
    return CVMFetcher()


def _make_zip_csv(csv_text: str, filename: str) -> bytes:
    """Cria um arquivo ZIP em memória contendo um CSV."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, csv_text)
    return buf.getvalue()


def _make_response(
    content: bytes | None = None, text: str | None = None, status: int = 200
):
    """Cria um mock de requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if content is not None:
        resp.content = content
    if text is not None:
        resp.text = text
    return resp


# =============================================================================
# get_company_registry
# =============================================================================


class TestGetCompanyRegistry:
    """Testes para get_company_registry."""

    def test_retorna_dataframe(self, fetcher):
        """Retorna DataFrame com colunas normalizadas."""
        csv_content = (
            "CNPJ_CIA;DENOM_SOCIAL;COD_CVM;SETOR_ATIV;SIT\n"
            "33.000.167/0001-01;PETROLEO BRASILEIRO SA;9512;Petróleo;A\n"
            "60.746.948/0001-12;ITAU UNIBANCO;14469;Financeiro;A\n"
        )
        resp = _make_response(text=csv_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_company_registry()

        assert isinstance(df, pd.DataFrame)
        assert "cnpj" in df.columns
        assert "razao_social" in df.columns
        assert len(df) == 2

    def test_colunas_renomeadas(self, fetcher):
        """Colunas CVM são renomeadas corretamente."""
        csv_content = (
            "CNPJ_CIA;DENOM_SOCIAL;COD_CVM;SETOR_ATIV;SIT\n"
            "33.000.167/0001-01;PETROBRAS;9512;Petróleo;A\n"
        )
        resp = _make_response(text=csv_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_company_registry()

        assert set(df.columns) >= {
            "cnpj",
            "razao_social",
            "cod_cvm",
            "setor",
            "situacao",
        }

    def test_url_correta(self, fetcher):
        """Faz request para a URL do cadastro CVM."""
        csv_content = "CNPJ_CIA;DENOM_SOCIAL;COD_CVM;SETOR_ATIV;SIT\n"
        resp = _make_response(text=csv_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp) as mock_fetch:
            fetcher.get_company_registry()

        url_chamado = mock_fetch.call_args[0][0]
        assert "cad_cia_aberta.csv" in url_chamado
        assert "CIA_ABERTA" in url_chamado


# =============================================================================
# build_ticker_cnpj_map
# =============================================================================


class TestBuildTickerCnpjMap:
    """Testes para build_ticker_cnpj_map."""

    def test_usa_ddm_como_fonte_primaria(self, fetcher):
        """Usa DDM asset list como fonte primária para o mapeamento."""
        assets_ddm = [
            {"ticker": "PETR4", "cnpj": "33.000.167/0001-01"},
            {"ticker": "VALE3", "cnpj": "33.592.510/0001-54"},
            {"ativo": "ITUB4", "cnpj": "60.872.504/0001-23"},
        ]

        with patch(
            "carteira_auto.data.fetchers.ddm_fetcher.DDMFetcher.get_asset_list",
            return_value=assets_ddm,
        ):
            mapping = fetcher.build_ticker_cnpj_map()

        assert mapping["PETR4"] == "33.000.167/0001-01"
        assert mapping["VALE3"] == "33.592.510/0001-54"
        assert mapping["ITUB4"] == "60.872.504/0001-23"

    def test_fallback_cvm_quando_ddm_falha(self, fetcher):
        """Usa CVM como fallback quando DDM lança exceção."""
        csv_content = (
            "CNPJ_CIA;DENOM_SOCIAL;COD_CVM;SETOR_ATIV;SIT\n"
            "33.000.167/0001-01;PETROBRAS;9512;Petróleo;A\n"
        )
        resp = _make_response(text=csv_content)

        with (
            patch(
                "carteira_auto.data.fetchers.ddm_fetcher.DDMFetcher.get_asset_list",
                side_effect=Exception("DDM indisponível"),
            ),
            patch.object(fetcher, "_fetch_raw", return_value=resp),
        ):
            mapping = fetcher.build_ticker_cnpj_map()

        # Fallback usa cod_cvm como chave (heurística)
        assert isinstance(mapping, dict)

    def test_tickers_normalizados_maiusculos(self, fetcher):
        """Tickers são normalizados para maiúsculas."""
        assets_ddm = [
            {"ticker": "petr4", "cnpj": "33.000.167/0001-01"},
        ]

        with patch(
            "carteira_auto.data.fetchers.ddm_fetcher.DDMFetcher.get_asset_list",
            return_value=assets_ddm,
        ):
            mapping = fetcher.build_ticker_cnpj_map()

        assert "PETR4" in mapping


# =============================================================================
# get_cnpj_by_ticker
# =============================================================================


class TestGetCnpjByTicker:
    """Testes para get_cnpj_by_ticker."""

    def test_retorna_cnpj_por_ticker_exato(self, fetcher):
        """Retorna CNPJ para ticker exato."""
        with patch.object(
            fetcher,
            "build_ticker_cnpj_map",
            return_value={"PETR4": "33.000.167/0001-01"},
        ):
            cnpj = fetcher.get_cnpj_by_ticker("PETR4")

        assert cnpj == "33.000.167/0001-01"

    def test_remove_sufixo_sa(self, fetcher):
        """Remove sufixo .SA antes de buscar."""
        with patch.object(
            fetcher,
            "build_ticker_cnpj_map",
            return_value={"PETR4": "33.000.167/0001-01"},
        ):
            cnpj = fetcher.get_cnpj_by_ticker("PETR4.SA")

        assert cnpj == "33.000.167/0001-01"

    def test_case_insensitive(self, fetcher):
        """Normaliza ticker para maiúsculas."""
        with patch.object(
            fetcher,
            "build_ticker_cnpj_map",
            return_value={"PETR4": "33.000.167/0001-01"},
        ):
            cnpj = fetcher.get_cnpj_by_ticker("petr4")

        assert cnpj == "33.000.167/0001-01"

    def test_retorna_none_quando_nao_encontrado(self, fetcher):
        """Retorna None para ticker inexistente."""
        with patch.object(fetcher, "build_ticker_cnpj_map", return_value={}):
            cnpj = fetcher.get_cnpj_by_ticker("TICKER_INEXISTENTE")

        assert cnpj is None

    def test_matching_por_base_ticker(self, fetcher):
        """Encontra CNPJ via base do ticker (PETR3 → mesmo CNPJ que PETR4)."""
        with patch.object(
            fetcher,
            "build_ticker_cnpj_map",
            return_value={"PETR4": "33.000.167/0001-01"},
        ):
            cnpj = fetcher.get_cnpj_by_ticker("PETR3")

        # PETR3 tem mesma base PETR que PETR4
        assert cnpj == "33.000.167/0001-01"


# =============================================================================
# get_dfp
# =============================================================================


class TestGetDfp:
    """Testes para get_dfp (DFP anual)."""

    DRE_CSV = (
        "CNPJ_CIA;DT_REFER;CD_CONTA;DS_CONTA;VL_CONTA\n"
        "33.000.167/0001-01;2024-12-31;3.01;Receita;500000000\n"
        "33.000.167/0001-01;2024-12-31;3.11;Lucro;100000000\n"
        "60.746.948/0001-12;2024-12-31;3.01;Receita;300000000\n"
    )

    def test_retorna_dataframe_filtrado(self, fetcher):
        """Retorna apenas linhas da empresa (CNPJ)."""
        zip_content = _make_zip_csv(self.DRE_CSV, "dfp_cia_aberta_DRE_con_2024.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_dfp("33.000.167/0001-01", 2024, "DRE")

        assert isinstance(df, pd.DataFrame)
        # Apenas 2 linhas da Petrobras
        assert len(df) == 2

    def test_url_com_ano_correto(self, fetcher):
        """URL inclui o ano da DFP."""
        zip_content = _make_zip_csv(self.DRE_CSV, "dfp_cia_aberta_DRE_con_2023.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp) as mock_fetch:
            fetcher.get_dfp("33.000.167/0001-01", 2023, "DRE")

        url = mock_fetch.call_args[0][0]
        assert "2023" in url
        assert "DFP" in url

    def test_statement_invalido_levanta_erro(self, fetcher):
        """Levanta ValueError para statement não suportado."""
        with pytest.raises(ValueError, match="Statement inválido"):
            fetcher.get_dfp("33.000.167/0001-01", 2024, "INEXISTENTE")

    def test_suporta_bpa(self, fetcher):
        """Aceita statement BPA."""
        bpa_csv = (
            "CNPJ_CIA;DT_REFER;CD_CONTA;DS_CONTA;VL_CONTA\n"
            "33.000.167/0001-01;2024-12-31;1.01;Ativo Circulante;200000000\n"
        )
        zip_content = _make_zip_csv(bpa_csv, "dfp_cia_aberta_BPA_con_2024.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_dfp("33.000.167/0001-01", 2024, "BPA")

        assert len(df) == 1

    @pytest.mark.parametrize("statement", ["BPA", "BPP", "DRE", "DFC_MD", "DVA"])
    def test_todos_statements_validos(self, fetcher, statement):
        """Todos os statements do _STATEMENT_MAP são aceitos."""
        csv = "CNPJ_CIA;DT_REFER;VL_CONTA\n33.000.167/0001-01;2024-12-31;100\n"
        filename = f"dfp_cia_aberta_{statement}_con_2024.csv"
        zip_content = _make_zip_csv(csv, filename)
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_dfp("33.000.167/0001-01", 2024, statement)

        assert isinstance(df, pd.DataFrame)


# =============================================================================
# get_itr
# =============================================================================


class TestGetItr:
    """Testes para get_itr (ITR trimestral)."""

    ITR_CSV = (
        "CNPJ_CIA;DT_REFER;CD_CONTA;DS_CONTA;VL_CONTA\n"
        "33.000.167/0001-01;2024-03-31;3.01;Receita;120000000\n"
        "33.000.167/0001-01;2024-06-30;3.01;Receita;130000000\n"
        "33.000.167/0001-01;2024-09-30;3.01;Receita;140000000\n"
    )

    def test_retorna_dataframe(self, fetcher):
        """Retorna DataFrame para o trimestre."""
        zip_content = _make_zip_csv(self.ITR_CSV, "itr_cia_aberta_DRE_con_2024.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_itr("33.000.167/0001-01", 2024, 1, "DRE")

        assert isinstance(df, pd.DataFrame)

    def test_quarter_invalido_levanta_erro(self, fetcher):
        """Levanta ValueError para trimestre inválido."""
        with pytest.raises(ValueError, match="Trimestre inválido"):
            fetcher.get_itr("33.000.167/0001-01", 2024, 5, "DRE")

    def test_quarter_zero_invalido(self, fetcher):
        """Trimestre 0 é inválido."""
        with pytest.raises(ValueError, match="Trimestre inválido"):
            fetcher.get_itr("33.000.167/0001-01", 2024, 0, "DRE")

    def test_statement_invalido_levanta_erro(self, fetcher):
        """Levanta ValueError para statement não suportado no ITR."""
        with pytest.raises(ValueError, match="Statement inválido para ITR"):
            fetcher.get_itr("33.000.167/0001-01", 2024, 1, "DVA")  # DVA não está no ITR

    @pytest.mark.parametrize("quarter", [1, 2, 3, 4])
    def test_todos_quarters_validos(self, fetcher, quarter):
        """Quarters 1-4 são aceitos."""
        zip_content = _make_zip_csv(self.ITR_CSV, "itr_cia_aberta_DRE_con_2024.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_itr("33.000.167/0001-01", 2024, quarter, "DRE")

        assert isinstance(df, pd.DataFrame)


# =============================================================================
# get_dfp_by_ticker / get_itr_by_ticker
# =============================================================================


class TestConvenienceMethods:
    """Testes para métodos de conveniência (por ticker)."""

    def test_get_dfp_by_ticker_resolve_cnpj(self, fetcher):
        """get_dfp_by_ticker resolve CNPJ automaticamente."""
        csv = "CNPJ_CIA;DT_REFER;VL_CONTA\n33.000.167/0001-01;2024-12-31;100\n"
        zip_content = _make_zip_csv(csv, "dfp_cia_aberta_DRE_con_2024.csv")
        resp = _make_response(content=zip_content)

        with (
            patch.object(
                fetcher, "get_cnpj_by_ticker", return_value="33.000.167/0001-01"
            ),
            patch.object(fetcher, "_fetch_raw", return_value=resp),
        ):
            df = fetcher.get_dfp_by_ticker("PETR4", 2024, "DRE")

        assert isinstance(df, pd.DataFrame)

    def test_get_dfp_by_ticker_levanta_erro_sem_cnpj(self, fetcher):
        """Levanta ValueError quando CNPJ não é encontrado."""
        with patch.object(fetcher, "get_cnpj_by_ticker", return_value=None):
            with pytest.raises(ValueError, match="CNPJ não encontrado"):
                fetcher.get_dfp_by_ticker("TICKER_INEXISTENTE", 2024, "DRE")

    def test_get_itr_by_ticker_resolve_cnpj(self, fetcher):
        """get_itr_by_ticker resolve CNPJ automaticamente."""
        csv = "CNPJ_CIA;DT_REFER;VL_CONTA\n33.000.167/0001-01;2024-03-31;100\n"
        zip_content = _make_zip_csv(csv, "itr_cia_aberta_DRE_con_2024.csv")
        resp = _make_response(content=zip_content)

        with (
            patch.object(
                fetcher, "get_cnpj_by_ticker", return_value="33.000.167/0001-01"
            ),
            patch.object(fetcher, "_fetch_raw", return_value=resp),
        ):
            df = fetcher.get_itr_by_ticker("PETR4", 2024, 1, "DRE")

        assert isinstance(df, pd.DataFrame)

    def test_get_itr_by_ticker_levanta_erro_sem_cnpj(self, fetcher):
        """Levanta ValueError quando CNPJ não é encontrado no ITR."""
        with patch.object(fetcher, "get_cnpj_by_ticker", return_value=None):
            with pytest.raises(ValueError, match="CNPJ não encontrado"):
                fetcher.get_itr_by_ticker("TICKER_INEXISTENTE", 2024, 1, "DRE")


# =============================================================================
# _filter_by_cnpj
# =============================================================================


class TestFilterByCnpj:
    """Testes para o método interno _filter_by_cnpj."""

    def test_filtra_por_cnpj_formatado(self):
        """Filtra por CNPJ com pontuação."""
        df = pd.DataFrame(
            {
                "cnpj_cia": [
                    "33.000.167/0001-01",
                    "60.746.948/0001-12",
                    "33.000.167/0001-01",
                ],
                "valor": [100, 200, 300],
            }
        )
        result = CVMFetcher._filter_by_cnpj(df, "33.000.167/0001-01")
        assert len(result) == 2

    def test_filtra_cnpj_sem_formatacao(self):
        """Filtra mesmo quando CNPJ no DF está sem pontuação."""
        df = pd.DataFrame(
            {
                "cnpj_cia": ["33000167000101", "60746948000112"],
                "valor": [100, 200],
            }
        )
        result = CVMFetcher._filter_by_cnpj(df, "33.000.167/0001-01")
        assert len(result) == 1

    def test_sem_coluna_cnpj_retorna_df_original(self):
        """Retorna DataFrame original quando não há coluna CNPJ."""
        df = pd.DataFrame({"valor": [100, 200]})
        result = CVMFetcher._filter_by_cnpj(df, "33.000.167/0001-01")
        assert len(result) == 2

    def test_resultado_vazio_para_cnpj_inexistente(self):
        """Retorna DataFrame vazio para CNPJ não presente."""
        df = pd.DataFrame(
            {
                "cnpj_cia": ["60.746.948/0001-12"],
                "valor": [100],
            }
        )
        result = CVMFetcher._filter_by_cnpj(df, "33.000.167/0001-01")
        assert len(result) == 0


# =============================================================================
# _fetch_zip_csv
# =============================================================================


class TestFetchZipCsv:
    """Testes para _fetch_zip_csv."""

    def test_extrai_csv_do_zip(self, fetcher):
        """Extrai e parseia CSV de dentro do ZIP."""
        csv = "col_a;col_b\nval1;val2\n"
        zip_content = _make_zip_csv(csv, "arquivo.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher._fetch_zip_csv("http://fake.url/test.zip", "arquivo.csv")

        assert isinstance(df, pd.DataFrame)
        assert "col_a" in df.columns
        assert len(df) == 1

    def test_busca_arquivo_case_insensitive(self, fetcher):
        """Encontra arquivo no ZIP independente de case."""
        csv = "a;b\n1;2\n"
        zip_content = _make_zip_csv(csv, "Arquivo_MAIUSCULO.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher._fetch_zip_csv(
                "http://fake.url/test.zip", "arquivo_maiusculo.csv"
            )

        assert isinstance(df, pd.DataFrame)

    def test_colunas_normalizadas_minusculas(self, fetcher):
        """Colunas são normalizadas para minúsculas."""
        csv = "COL_MAIUSCULA;OUTRA_COL\nval1;val2\n"
        zip_content = _make_zip_csv(csv, "test.csv")
        resp = _make_response(content=zip_content)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher._fetch_zip_csv("http://fake.url/test.zip", "test.csv")

        assert "col_maiuscula" in df.columns
        assert "outra_col" in df.columns


# =============================================================================
# Testes de integração
# =============================================================================


@pytest.mark.integration
class TestCVMFetcherIntegration:
    """Testes de integração — requerem conectividade com dados.cvm.gov.br."""

    def test_get_company_registry_retorna_dados_reais(self):
        """Cadastro CVM retorna companhias reais (requer internet)."""
        fetcher = CVMFetcher()
        df = fetcher.get_company_registry()

        assert len(df) > 100
        assert "cnpj" in df.columns
        assert "razao_social" in df.columns

    def test_get_cnpj_petrobras(self):
        """Petrobras tem CNPJ mapeável."""
        fetcher = CVMFetcher()
        cnpj = fetcher.get_cnpj_by_ticker("PETR4")

        # CNPJ da Petrobras: 33.000.167/0001-01
        assert cnpj is not None
        assert "33" in cnpj.replace(".", "").replace("/", "").replace("-", "")

    def test_get_dfp_dre_petrobras(self):
        """DRE anual da Petrobras tem linhas de receita."""
        fetcher = CVMFetcher()
        cnpj = "33.000.167/0001-01"

        df = fetcher.get_dfp(cnpj, 2023, "DRE")

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
