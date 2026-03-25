"""Testes para FREDFetcher — Federal Reserve Economic Data.

Cobertura:
    - Unit: mocks de requests.get (sem rede, sem API key)
    - Integration: @pytest.mark.integration (requer FRED_API_KEY)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from carteira_auto.data.fetchers.fred_fetcher import (
    FRED_MACRO_BUNDLE,
    FRED_SERIES,
    FREDFetcher,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fetcher():
    """FREDFetcher com API key fake para testes de unidade."""
    f = FREDFetcher()
    f._api_key = "fake-fred-key-for-tests"
    return f


def _make_fred_response(series_id: str, n: int = 5) -> dict:
    """Cria resposta FRED com n observações fictícias."""
    return {
        "observations": [
            {
                "date": f"2025-0{i+1}-01",
                "value": str(4.5 + i * 0.1),
            }
            for i in range(n)
        ]
    }


def _make_mock_response(data: dict, status: int = 200):
    """Cria mock de requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json.return_value = data
    return resp


# =============================================================================
# TestFREDFetcherInit
# =============================================================================


class TestFREDFetcherInit:
    """Testes de inicialização."""

    def test_sem_api_key_nao_levanta_erro(self):
        """FREDFetcher pode ser instanciado sem API key (loga aviso)."""
        f = FREDFetcher()
        assert f._api_key is None or isinstance(f._api_key, str)

    def test_com_api_key_configura_corretamente(self):
        """API key é setada corretamente."""
        f = FREDFetcher()
        f._api_key = "test-key"
        assert f._api_key == "test-key"

    def test_url_base_configurada(self):
        """URL base do FRED é configurada via settings."""
        f = FREDFetcher()
        assert "stlouisfed" in f._base_url


# =============================================================================
# TestGetSeries
# =============================================================================


class TestGetSeries:
    """Testes para get_series."""

    def test_retorna_dataframe_com_colunas_corretas(self, fetcher):
        """Retorna DataFrame com date, value, series_id."""
        data = _make_fred_response("DFF", n=3)
        resp = _make_mock_response(data)

        with patch("requests.get", return_value=resp):
            df = fetcher.get_series("DFF")

        assert isinstance(df, pd.DataFrame)
        assert "date" in df.columns
        assert "value" in df.columns
        assert "series_id" in df.columns

    def test_coluna_series_id_preenchida(self, fetcher):
        """Coluna series_id contém o código da série."""
        data = _make_fred_response("DGS10")
        resp = _make_mock_response(data)

        with patch("requests.get", return_value=resp):
            df = fetcher.get_series("DGS10")

        assert (df["series_id"] == "DGS10").all()

    def test_date_convertido_para_datetime(self, fetcher):
        """Coluna date é dtype datetime."""
        data = _make_fred_response("DFF")
        resp = _make_mock_response(data)

        with patch("requests.get", return_value=resp):
            df = fetcher.get_series("DFF")

        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_value_convertido_para_float(self, fetcher):
        """Coluna value é numérica."""
        data = _make_fred_response("DFF")
        resp = _make_mock_response(data)

        with patch("requests.get", return_value=resp):
            df = fetcher.get_series("DFF")

        assert pd.api.types.is_numeric_dtype(df["value"])

    def test_missing_values_removidos(self, fetcher):
        """Valores '.' do FRED são convertidos para NaN e removidos."""
        data = {
            "observations": [
                {"date": "2025-01-01", "value": "4.5"},
                {"date": "2025-02-01", "value": "."},  # FRED missing
                {"date": "2025-03-01", "value": "4.7"},
            ]
        }
        resp = _make_mock_response(data)

        with patch("requests.get", return_value=resp):
            df = fetcher.get_series("DFF")

        # Linha com "." deve ser removida
        assert len(df) == 2
        assert df["value"].notna().all()

    def test_serie_vazia_retorna_df_sem_linhas(self, fetcher):
        """Série sem observações retorna DataFrame vazio com colunas corretas."""
        data = {"observations": []}
        resp = _make_mock_response(data)

        # Usa série exclusiva para este teste para evitar colisão com cache
        with patch("requests.get", return_value=resp):
            df = fetcher.get_series("SERIE_VAZIA_TESTE_EXCLUSIVO")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert set(df.columns) >= {"date", "value", "series_id"}

    def test_sem_api_key_levanta_permissionerror(self):
        """Levanta PermissionError quando API key não está configurada."""
        f = FREDFetcher()
        f._api_key = None

        # Série exclusiva para evitar colisão com cache de outros testes
        with pytest.raises(PermissionError, match="FRED API key"):
            f.get_series("DFF_SEM_KEY_EXCLUSIVO")

    def test_passa_parametros_corretos_para_api(self, fetcher):
        """Passa series_id, datas e api_key nos params."""
        data = _make_fred_response("VIXCLS")
        resp = _make_mock_response(data)

        with patch("requests.get", return_value=resp) as mock_get:
            fetcher.get_series("VIXCLS", start_date="2024-01-01", end_date="2025-01-01")

        call_params = mock_get.call_args[1]["params"]
        assert call_params["series_id"] == "VIXCLS"
        assert call_params["observation_start"] == "2024-01-01"
        assert call_params["observation_end"] == "2025-01-01"
        assert call_params["api_key"] == "fake-fred-key-for-tests"

    def test_erro_autenticacao_400(self, fetcher):
        """HTTP 400 levanta PermissionError."""
        resp = _make_mock_response({}, status=400)

        with patch("requests.get", return_value=resp):
            with pytest.raises(PermissionError, match="autenticação"):
                fetcher.get_series("DFF")

    def test_serie_nao_encontrada_404(self, fetcher):
        """HTTP 404 levanta HTTPError."""
        import requests as req

        resp = _make_mock_response({}, status=404)

        with patch("requests.get", return_value=resp):
            with pytest.raises(req.HTTPError):
                fetcher.get_series("SERIE_INEXISTENTE")


# =============================================================================
# TestGetMultipleSeries
# =============================================================================


class TestGetMultipleSeries:
    """Testes para get_multiple_series."""

    def test_retorna_dict_com_series(self, fetcher):
        """Retorna dict {series_id: DataFrame}."""
        data = _make_fred_response("DFF")
        resp = _make_mock_response(data)

        with patch("requests.get", return_value=resp):
            result = fetcher.get_multiple_series(["DFF", "DGS10"])

        assert isinstance(result, dict)
        # Pode ter 1 ou 2 — mock retorna mesmo dado para ambos
        assert len(result) >= 1

    def test_erro_em_uma_serie_nao_impede_outras(self, fetcher):
        """Erro em uma série não impede o processamento das demais."""
        good_data = _make_fred_response("DGS10")

        def side_effect(url, params, timeout):
            if params.get("series_id") == "SERIE_RUIM":
                raise Exception("Erro simulado")
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = good_data
            return resp

        with patch("requests.get", side_effect=side_effect):
            # Substitui get_series por mock mais simples
            with patch.object(fetcher, "get_series") as mock_gs:
                mock_gs.side_effect = lambda sid, **kw: (
                    pd.DataFrame(
                        {"date": ["2025-01-01"], "value": [4.5], "series_id": [sid]}
                    )
                    if sid != "SERIE_RUIM"
                    else (_ for _ in ()).throw(Exception("erro"))
                )
                result = fetcher.get_multiple_series(["DGS10", "SERIE_RUIM"])

        assert "DGS10" in result
        assert "SERIE_RUIM" not in result


# =============================================================================
# TestGetMacroBundle
# =============================================================================


class TestGetMacroBundle:
    """Testes para get_macro_bundle."""

    def test_usa_bundle_padrao(self, fetcher):
        """Chama get_multiple_series com FRED_MACRO_BUNDLE."""
        with patch.object(fetcher, "get_multiple_series", return_value={}) as mock_ms:
            fetcher.get_macro_bundle()

        called_ids = mock_ms.call_args[0][0]
        for sid in FRED_MACRO_BUNDLE:
            assert sid in called_ids

    def test_retorna_dict(self, fetcher):
        """Retorna dict (mesmo que vazio)."""
        with patch.object(fetcher, "get_multiple_series", return_value={}):
            result = fetcher.get_macro_bundle()

        assert isinstance(result, dict)


# =============================================================================
# TestConvenienceMethods
# =============================================================================


class TestConvenienceMethods:
    """Testes para métodos de conveniência."""

    @pytest.mark.parametrize(
        "method,expected_series",
        [
            ("get_fed_funds_rate", "DFF"),
            ("get_treasury_10y", "DGS10"),
            ("get_treasury_2y", "DGS2"),
            ("get_yield_curve_spread", "T10Y2Y"),
            ("get_vix", "VIXCLS"),
            ("get_us_cpi", "CPIAUCSL"),
            ("get_core_pce", "PCEPILFE"),
            ("get_brl_usd", "DEXBZUS"),
            ("get_us_unemployment", "UNRATE"),
            ("get_high_yield_spread", "BAMLH0A0HYM2"),
            ("get_breakeven_inflation", "T10YIE"),
        ],
    )
    def test_convenience_method_chama_serie_correta(
        self, fetcher, method, expected_series
    ):
        """Cada método de conveniência chama get_series com a série correta."""
        with patch.object(
            fetcher, "get_series", return_value=pd.DataFrame()
        ) as mock_gs:
            getattr(fetcher, method)()

        mock_gs.assert_called_once_with(expected_series)

    def test_get_us_gdp_real_usa_gdpc1(self, fetcher):
        """get_us_gdp(real=True) usa GDPC1."""
        with patch.object(
            fetcher, "get_series", return_value=pd.DataFrame()
        ) as mock_gs:
            fetcher.get_us_gdp(real=True)

        mock_gs.assert_called_once_with("GDPC1")

    def test_get_us_gdp_nominal_usa_gdp(self, fetcher):
        """get_us_gdp(real=False) usa GDP."""
        with patch.object(
            fetcher, "get_series", return_value=pd.DataFrame()
        ) as mock_gs:
            fetcher.get_us_gdp(real=False)

        mock_gs.assert_called_once_with("GDP")

    def test_list_series_retorna_dict(self):
        """list_series retorna dicionário com séries disponíveis."""
        series = FREDFetcher.list_series()
        assert isinstance(series, dict)
        assert len(series) >= 10
        assert "DFF" in series
        assert "DGS10" in series
        assert "VIXCLS" in series


# =============================================================================
# TestFredSeriesConstants
# =============================================================================


class TestFredSeriesConstants:
    """Testes para as constantes de séries."""

    def test_fred_series_tem_campos_obrigatorios(self):
        """Cada série tem nome, unidade e frequencia."""
        for series_id, info in FRED_SERIES.items():
            assert "nome" in info, f"{series_id} sem campo 'nome'"
            assert "unidade" in info, f"{series_id} sem campo 'unidade'"
            assert "frequencia" in info, f"{series_id} sem campo 'frequencia'"

    def test_macro_bundle_esta_em_fred_series(self):
        """Todas as séries do bundle padrão estão no catálogo."""
        for sid in FRED_MACRO_BUNDLE:
            assert sid in FRED_SERIES, f"{sid} do bundle não está em FRED_SERIES"

    def test_brl_usd_incluido(self):
        """DEXBZUS (BRL/USD) está disponível — relevante para carteira BR."""
        assert "DEXBZUS" in FRED_SERIES

    def test_vix_incluido(self):
        """VIXCLS está disponível."""
        assert "VIXCLS" in FRED_SERIES


# =============================================================================
# Testes de integração
# =============================================================================


@pytest.mark.integration
class TestFREDFetcherIntegration:
    """Testes de integração — requerem FRED_API_KEY."""

    @pytest.fixture(autouse=True)
    def skip_if_no_key(self):
        """Pula se FRED_API_KEY não estiver configurada."""
        if not os.getenv("FRED_API_KEY"):
            pytest.skip("FRED_API_KEY não configurada")

    def test_get_fed_funds_rate_retorna_dados_reais(self):
        """Fed Funds Rate retorna série com dados reais."""
        fetcher = FREDFetcher()
        df = fetcher.get_fed_funds_rate()

        assert len(df) > 100
        assert "date" in df.columns
        assert "value" in df.columns
        assert df["value"].notna().all()

    def test_get_vix_retorna_dados_reais(self):
        """VIX retorna série com dados reais."""
        fetcher = FREDFetcher()
        df = fetcher.get_vix()

        assert len(df) > 100
        assert df["value"].min() > 0  # VIX é sempre positivo

    def test_get_brl_usd_retorna_dados_reais(self):
        """BRL/USD retorna série com dados reais."""
        fetcher = FREDFetcher()
        df = fetcher.get_brl_usd()

        assert len(df) > 50
        # BRL/USD deve estar numa faixa razoável
        assert df["value"].min() > 1.0
        assert df["value"].max() < 20.0

    def test_get_macro_bundle_retorna_multiplas_series(self):
        """Bundle macro retorna pelo menos 4 séries."""
        fetcher = FREDFetcher()
        bundle = fetcher.get_macro_bundle()

        assert len(bundle) >= 4
        assert isinstance(bundle, dict)
        for df in bundle.values():
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
