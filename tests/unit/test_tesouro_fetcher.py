"""Testes para TesouroDiretoFetcher — dados abertos do Tesouro Transparente.

Cobertura:
    - Unit: mocks de requests.get (sem rede)
    - Integration: @pytest.mark.integration (requer conectividade)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from carteira_auto.data.fetchers.tesouro_fetcher import TesouroDiretoFetcher

# =============================================================================
# Fixtures / helpers
# =============================================================================


@pytest.fixture
def fetcher():
    """TesouroDiretoFetcher sem dependências externas."""
    return TesouroDiretoFetcher()


_CSV_TESOURO = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha\n"
    "LFT;01/03/2029;24/03/2025;0,12;0,13;14500,00;14550,00;14510,00\n"
    "NTN-B Principal;15/05/2035;24/03/2025;7,25;7,30;3200,00;3210,00;3205,00\n"
    "NTN-B;15/08/2040;24/03/2025;6,80;6,85;4100,00;4110,00;4105,00\n"
    "LTN;01/01/2027;24/03/2025;13,50;13,55;850,00;851,00;850,50\n"
    "NTN-F;01/01/2033;24/03/2025;13,20;13,25;1050,00;1055,00;1052,00\n"
    # Linha de data anterior para testar filtro de última data
    "LFT;01/03/2029;23/03/2025;0,11;0,12;14490,00;14540,00;14500,00\n"
)


def _make_response(text: str, status: int = 200):
    """Cria mock de requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.text = text
    return resp


# =============================================================================
# TestGetCurrentRates
# =============================================================================


class TestGetCurrentRates:
    """Testes para get_current_rates."""

    def test_retorna_dataframe(self, fetcher):
        """Retorna DataFrame com dados de títulos."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_current_rates()

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_filtra_apenas_data_mais_recente(self, fetcher):
        """Retorna apenas linhas da data mais recente."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_current_rates()

        # CSV tem 2 datas: 24/03/2025 e 23/03/2025 — deve retornar apenas 24/03
        assert df["data"].nunique() == 1
        assert df["data"].iloc[0] == pd.Timestamp("2025-03-24")

    def test_colunas_normalizadas(self, fetcher):
        """Colunas são renomeadas para nomes padronizados."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_current_rates()

        assert "tipo" in df.columns
        assert "vencimento" in df.columns
        assert "taxa_compra" in df.columns
        assert "taxa_venda" in df.columns


# =============================================================================
# TestGetPriceHistory
# =============================================================================


class TestGetPriceHistory:
    """Testes para get_price_history."""

    def test_retorna_dataframe_completo(self, fetcher):
        """Retorna DataFrame com todos os títulos."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history()

        # CSV tem 6 linhas (5 títulos + 1 LFT de data anterior)
        assert len(df) == 6

    def test_data_convertida_para_datetime(self, fetcher):
        """Coluna data é dtype datetime."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history()

        assert pd.api.types.is_datetime64_any_dtype(df["data"])

    def test_taxas_convertidas_para_float(self, fetcher):
        """Colunas de taxa e PU são numéricas."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history()

        for col in ["taxa_compra", "taxa_venda", "pu_compra", "pu_venda"]:
            if col in df.columns:
                assert pd.api.types.is_numeric_dtype(df[col]), f"{col} não é numérico"


# =============================================================================
# TestGetPriceHistoryByType
# =============================================================================


class TestGetPriceHistoryByType:
    """Testes para get_price_history_by_type."""

    def test_filtra_lft(self, fetcher):
        """Filtra apenas LFT."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history_by_type("LFT")

        assert len(df) > 0
        assert df["tipo"].str.contains("LFT").all()

    def test_filtra_ntnb_principal(self, fetcher):
        """Filtra NTN-B Principal (sem cupom)."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history_by_type("NTN-B")

        assert len(df) > 0
        assert df["tipo"].str.contains("Principal").all()

    def test_filtra_ntnb_com_cupom(self, fetcher):
        """Filtra NTN-B com cupom (não Principal)."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history_by_type("NTN-B CUPOM")

        assert len(df) > 0
        # Não deve conter "Principal"
        assert not df["tipo"].str.contains("Principal").any()

    def test_filtra_ltn(self, fetcher):
        """Filtra apenas LTN."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history_by_type("LTN")

        assert len(df) > 0
        assert df["tipo"].str.contains("LTN").all()

    def test_tipo_invalido_levanta_erro(self, fetcher):
        """Tipo não reconhecido levanta ValueError."""
        with pytest.raises(ValueError, match="Tipo"):
            fetcher.get_price_history_by_type("TIPO_INEXISTENTE")

    def test_case_insensitive(self, fetcher):
        """Tipo é case-insensitive."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history_by_type("lft")

        assert len(df) > 0

    @pytest.mark.parametrize("tipo", ["LFT", "NTN-B", "NTN-B CUPOM", "LTN", "NTN-F"])
    def test_todos_tipos_validos(self, fetcher, tipo):
        """Todos os tipos do _TIPO_MAP são aceitos."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            df = fetcher.get_price_history_by_type(tipo)

        assert isinstance(df, pd.DataFrame)


# =============================================================================
# TestConvenienceMethods
# =============================================================================


class TestConvenienceMethods:
    """Testes para métodos de conveniência."""

    def test_get_lft_history(self, fetcher):
        """get_lft_history chama get_price_history_by_type('LFT')."""
        with patch.object(
            fetcher, "get_price_history_by_type", return_value=pd.DataFrame()
        ) as mock:
            fetcher.get_lft_history()
        mock.assert_called_once_with("LFT")

    def test_get_ntnb_history_sem_cupom(self, fetcher):
        """get_ntnb_history() chama com 'NTN-B' (sem cupom)."""
        with patch.object(
            fetcher, "get_price_history_by_type", return_value=pd.DataFrame()
        ) as mock:
            fetcher.get_ntnb_history(com_cupom=False)
        mock.assert_called_once_with("NTN-B")

    def test_get_ntnb_history_com_cupom(self, fetcher):
        """get_ntnb_history(com_cupom=True) chama com 'NTN-B CUPOM'."""
        with patch.object(
            fetcher, "get_price_history_by_type", return_value=pd.DataFrame()
        ) as mock:
            fetcher.get_ntnb_history(com_cupom=True)
        mock.assert_called_once_with("NTN-B CUPOM")

    def test_get_ltn_history(self, fetcher):
        """get_ltn_history chama get_price_history_by_type('LTN')."""
        with patch.object(
            fetcher, "get_price_history_by_type", return_value=pd.DataFrame()
        ) as mock:
            fetcher.get_ltn_history()
        mock.assert_called_once_with("LTN")

    def test_get_ntnf_history(self, fetcher):
        """get_ntnf_history chama get_price_history_by_type('NTN-F')."""
        with patch.object(
            fetcher, "get_price_history_by_type", return_value=pd.DataFrame()
        ) as mock:
            fetcher.get_ntnf_history()
        mock.assert_called_once_with("NTN-F")


# =============================================================================
# TestGetNtnbCurve
# =============================================================================


class TestGetNtnbCurve:
    """Testes para get_ntnb_curve."""

    def test_retorna_snapshot_data_mais_recente(self, fetcher):
        """Retorna apenas a última data disponível."""
        df_ntnb = pd.DataFrame(
            {
                "tipo": ["NTN-B", "NTN-B", "NTN-B"],
                "vencimento": pd.to_datetime(
                    ["2030-05-15", "2035-05-15", "2040-05-15"]
                ),
                "data": pd.to_datetime(["2025-03-24", "2025-03-24", "2025-03-23"]),
                "taxa_compra": [6.5, 6.8, 7.0],
                "pu_compra": [3100.0, 3200.0, 3300.0],
            }
        )

        with patch.object(fetcher, "get_ntnb_history", return_value=df_ntnb):
            curve = fetcher.get_ntnb_curve()

        # Apenas 2 linhas com data 2025-03-24
        assert len(curve) == 2

    def test_ordenado_por_vencimento(self, fetcher):
        """Curva é ordenada por vencimento crescente."""
        df_ntnb = pd.DataFrame(
            {
                "tipo": ["NTN-B", "NTN-B", "NTN-B"],
                "vencimento": pd.to_datetime(
                    ["2040-05-15", "2030-05-15", "2035-05-15"]
                ),
                "data": pd.to_datetime(["2025-03-24", "2025-03-24", "2025-03-24"]),
                "taxa_compra": [7.0, 6.5, 6.8],
                "pu_compra": [3300.0, 3100.0, 3200.0],
            }
        )

        with patch.object(fetcher, "get_ntnb_history", return_value=df_ntnb):
            curve = fetcher.get_ntnb_curve()

        vencimentos = curve["vencimento"].tolist()
        assert vencimentos == sorted(vencimentos)


# =============================================================================
# TestGetAvailableTitles
# =============================================================================


class TestGetAvailableTitles:
    """Testes para get_available_titles."""

    def test_retorna_lista_de_tipos(self, fetcher):
        """Retorna lista com tipos de títulos únicos."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            titles = fetcher.get_available_titles()

        assert isinstance(titles, list)
        assert len(titles) > 0
        assert "LFT" in titles

    def test_lista_ordenada(self, fetcher):
        """Lista de títulos é ordenada alfabeticamente."""
        resp = _make_response(_CSV_TESOURO)

        with patch.object(fetcher, "_fetch_raw", return_value=resp):
            titles = fetcher.get_available_titles()

        assert titles == sorted(titles)


# =============================================================================
# Testes de integração
# =============================================================================


@pytest.mark.integration
class TestTesouroDiretoIntegration:
    """Testes de integração — requerem conectividade com tesourotransparente.gov.br."""

    def test_get_current_rates_retorna_dados_reais(self):
        """Taxas atuais retornam dados reais do Tesouro Transparente."""
        fetcher = TesouroDiretoFetcher()
        df = fetcher.get_current_rates()

        assert len(df) > 0
        assert "tipo" in df.columns
        assert "taxa_compra" in df.columns

    def test_get_lft_history_retorna_serie(self):
        """LFT tem histórico disponível."""
        fetcher = TesouroDiretoFetcher()
        df = fetcher.get_lft_history()

        assert len(df) > 100  # LFT existe desde 2002
        assert "taxa_compra" in df.columns

    def test_get_ntnb_curve_retorna_curva(self):
        """Curva NTN-B retorna múltiplos vértices."""
        fetcher = TesouroDiretoFetcher()
        curve = fetcher.get_ntnb_curve()

        assert len(curve) >= 3  # Pelo menos 3 vencimentos disponíveis
        assert curve["vencimento"].is_monotonic_increasing
