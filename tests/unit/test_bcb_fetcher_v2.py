"""Testes do BCBFetcher v2 — motor bcb.sgs + Expectativas + PTAX + TaxaJuros.

Cobre:
    - Motor SGS: bcb.sgs (primário) e fallback HTTP
    - Novos métodos de conveniência SGS (séries adicionadas na Fase A)
    - Focus (Expectativas): projeções anuais e IPCA 12m
    - PTAX: moeda específica, todas as moedas, lista de moedas
    - TaxaJuros: por modalidade, todas as modalidades, lista de modalidades
    - Backward compatibility: get_ptax(), get_ptax_venda() ainda funcionam
    - Error handling: fallback HTTP quando bcb.sgs falha
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from carteira_auto.config.constants import constants
from carteira_auto.data.fetchers.bcb import BCBFetcher

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def fetcher() -> BCBFetcher:
    return BCBFetcher()


def _make_sgs_df(values: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    """Cria DataFrame no formato retornado por bcb.sgs.get()."""
    dates = pd.date_range(start=start, periods=len(values), freq="D")
    df = pd.DataFrame({"valor": values}, index=dates)
    df.index.name = "Date"
    return df


def _make_focus_df() -> pd.DataFrame:
    """Cria DataFrame no formato retornado pelo endpoint ExpectativasMercadoAnuais."""
    return pd.DataFrame(
        {
            "Indicador": ["IPCA", "IPCA"],
            "IndicadorDetalhe": [None, None],
            "Data": ["2024-01-05", "2024-01-12"],
            "DataReferencia": ["2024", "2024"],
            "Mediana": [4.0, 3.9],
            "Media": [4.1, 4.0],
            "DesvioPadrao": [0.3, 0.3],
            "Minimo": [3.5, 3.4],
            "Maximo": [5.0, 4.9],
            "numeroRespondentes": [120, 118],
            "baseCalculo": [0, 0],
        }
    )


def _make_focus_ipca12m_df() -> pd.DataFrame:
    """Cria DataFrame no formato retornado pelo endpoint ExpectativasMercadoInflacao12Meses."""
    return pd.DataFrame(
        {
            "Indicador": ["IPCA", "IPCA"],
            "Data": ["2024-01-05", "2024-01-12"],
            "Suavizada": ["S", "S"],
            "Mediana": [4.5, 4.4],
            "Media": [4.6, 4.5],
            "DesvioPadrao": [0.4, 0.4],
            "Minimo": [3.8, 3.7],
            "Maximo": [5.5, 5.4],
            "numeroRespondentes": [100, 98],
            "baseCalculo": [0, 0],
        }
    )


def _make_ptax_df() -> pd.DataFrame:
    """Cria DataFrame no formato retornado pelo endpoint CotacaoMoedaPeriodo."""
    return pd.DataFrame(
        {
            "cotacaoCompra": [4.95, 4.97, 5.00],
            "cotacaoVenda": [4.96, 4.98, 5.01],
            "dataHoraCotacao": [
                "2024-01-03 13:14:41.000",
                "2024-01-04 13:05:35.000",
                "2024-01-05 13:10:31.000",
            ],
        }
    )


def _make_ptax_moedas_df() -> pd.DataFrame:
    """Cria DataFrame no formato retornado pelo endpoint Moedas."""
    return pd.DataFrame(
        {
            "simbolo": ["USD", "EUR", "GBP"],
            "nomeFormatado": ["Dólar dos Estados Unidos", "Euro", "Libra Esterlina"],
            "tipoMoeda": ["A", "B", "B"],
        }
    )


def _make_ptax_dia_df() -> pd.DataFrame:
    """Cria DataFrame no formato retornado pelo endpoint CotacaoMoedaDia."""
    return pd.DataFrame(
        {
            "cotacaoCompra": [4.95],
            "cotacaoVenda": [4.96],
        }
    )


def _make_taxa_juros_df() -> pd.DataFrame:
    """Cria DataFrame no formato retornado pelo endpoint TaxasJurosMensalPorMes."""
    return pd.DataFrame(
        {
            "Mes": ["Jan-2024", "Jan-2024", "Fev-2024"],
            "Modalidade": ["Cheque especial", "Crédito pessoal", "Cheque especial"],
            "Posicao": [1, 1, 1],
            "InstituicaoFinanceira": ["Banco A", "Banco B", "Banco A"],
            "TaxaJurosAoMes": [9.5, 3.2, 9.8],
            "TaxaJurosAoAno": [198.5, 45.2, 209.0],
            "cnpj8": ["12345678", "87654321", "12345678"],
            "anoMes": ["2024-01", "2024-01", "2024-02"],
        }
    )


def _make_params_consulta_df() -> pd.DataFrame:
    """Cria DataFrame no formato retornado pelo endpoint ParametrosConsulta."""
    return pd.DataFrame(
        {
            "codigoModalidade": [218, 219],
            "modalidade": ["Cheque especial", "Crédito pessoal"],
            "codigoSegmento": [1, 1],
            "segmento": ["PF", "PF"],
            "tipoModalidade": ["Rotativo", "Não-rotativo"],
        }
    )


# ============================================================================
# SEÇÃO 1-7: MÉTODOS SGS — motor bcb.sgs primário
# ============================================================================


class TestSGSPrimario:
    """Testa que os métodos SGS usam bcb.sgs como motor primário."""

    def test_get_selic_usa_bcb_sgs(self, fetcher: BCBFetcher) -> None:
        """get_selic() deve chamar bcb.sgs e retornar DataFrame normalizado."""
        mock_df = _make_sgs_df([11.75, 11.75, 11.50])

        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_selic(period_days=30)

        assert list(result.columns) == ["data", "valor"]
        assert len(result) == 3
        assert result["valor"].iloc[0] == 11.75

    def test_get_cdi_retorna_formato_correto(self, fetcher: BCBFetcher) -> None:
        """get_cdi() deve retornar DataFrame com colunas ['data', 'valor']."""
        mock_df = _make_sgs_df([0.05, 0.05])

        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_cdi(period_days=30)

        assert list(result.columns) == ["data", "valor"]
        assert pd.api.types.is_datetime64_any_dtype(result["data"])

    def test_get_ipca_retorna_dataframe(self, fetcher: BCBFetcher) -> None:
        """get_ipca() deve retornar DataFrame não-vazio."""
        mock_df = _make_sgs_df([0.52, 0.48, 0.61])

        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_ipca()

        assert not result.empty
        assert result["valor"].iloc[0] == 0.52

    def test_get_igpm_retorna_dataframe(self, fetcher: BCBFetcher) -> None:
        mock_df = _make_sgs_df([0.35, 0.40])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_igpm()
        assert not result.empty

    def test_get_ptax_backward_compat(self, fetcher: BCBFetcher) -> None:
        """get_ptax() deve continuar funcionando (backward compatibility)."""
        mock_df = _make_sgs_df([4.95, 4.97])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_ptax()
        assert list(result.columns) == ["data", "valor"]

    def test_get_ptax_venda_backward_compat(self, fetcher: BCBFetcher) -> None:
        """get_ptax_venda() deve continuar funcionando (backward compatibility)."""
        mock_df = _make_sgs_df([4.96, 4.98])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_ptax_venda()
        assert list(result.columns) == ["data", "valor"]

    def test_sgs_vazio_retorna_dataframe_vazio(self, fetcher: BCBFetcher) -> None:
        """Quando bcb.sgs retorna DataFrame vazio, deve retornar DataFrame vazio."""
        empty_df = pd.DataFrame(columns=["valor"])
        empty_df.index.name = "Date"

        with patch("bcb.sgs.get", return_value=empty_df):
            result = fetcher._fetch_via_bcb_sgs(432, date(2024, 1, 1), date(2024, 1, 5))

        assert result.empty
        assert list(result.columns) == ["data", "valor"]


class TestSGSNovosMethods:
    """Testa os novos métodos de conveniência SGS adicionados na Fase A."""

    @pytest.mark.parametrize(
        "method_name",
        [
            "get_cdi_annual",
            "get_real_effective_exchange",
            "get_gross_debt_gdp",
            "get_net_debt_gdp",
            "get_primary_result_gdp",
            "get_nominal_result",
            "get_nominal_interest_gdp",
            "get_ibcbr",
            "get_business_confidence",
            "get_embi",
            "get_ibovespa_bcb",
            "get_ouro_bmf",
            "get_credit_gdp",
            "get_default_rate",
            "get_m1",
            "get_m2",
            "get_m4",
            "get_trade_balance",
            "get_international_reserves",
        ],
    )
    def test_novo_metodo_retorna_dataframe(
        self, fetcher: BCBFetcher, method_name: str
    ) -> None:
        """Cada novo método deve chamar bcb.sgs e retornar DataFrame normalizado."""
        mock_df = _make_sgs_df([100.0, 101.0, 99.5])

        with patch("bcb.sgs.get", return_value=mock_df):
            method = getattr(fetcher, method_name)
            result = method()

        assert list(result.columns) == ["data", "valor"]
        assert len(result) == 3


class TestSGSFallbackHTTP:
    """Testa o fallback HTTP quando bcb.sgs falha."""

    def test_fallback_http_quando_bcb_sgs_falha(self, fetcher: BCBFetcher) -> None:
        """Quando bcb.sgs falha, deve usar HTTP SGS como fallback."""
        http_response = [
            {"data": "01/01/2024", "valor": "11.75"},
            {"data": "02/01/2024", "valor": "11.75"},
        ]

        with patch("bcb.sgs.get", side_effect=Exception("bcb.sgs unavailable")):
            with patch("requests.get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = http_response
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                result = fetcher._fetch_sgs_raw(432, date(2024, 1, 1), date(2024, 1, 5))

        assert not result.empty
        assert list(result.columns) == ["data", "valor"]
        assert result["valor"].iloc[0] == 11.75

    def test_fallback_http_retorna_vazio_quando_sem_dados(
        self, fetcher: BCBFetcher
    ) -> None:
        """Fallback HTTP deve retornar DataFrame vazio quando API retorna lista vazia."""
        with patch("bcb.sgs.get", side_effect=Exception("bcb offline")):
            with patch("requests.get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = []
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                result = fetcher._fetch_sgs_raw(432, date(2024, 1, 1), date(2024, 1, 5))

        assert result.empty

    def test_serie_nao_configurada_levanta_valueerror(
        self, fetcher: BCBFetcher
    ) -> None:
        """Série não presente em BCB_SERIES_CODES deve levantar ValueError."""
        with pytest.raises(ValueError, match="não configurada"):
            fetcher._fetch_sgs_series("serie_inexistente")


# ============================================================================
# SEÇÃO 8: FOCUS — EXPECTATIVAS DE MERCADO
# ============================================================================


class TestFocus:
    """Testa os métodos Focus via bcb.Expectativas."""

    def _setup_focus_mock(self, mock_endpoint_data: pd.DataFrame):
        """Monta o mock do OData endpoint do Focus."""
        mock_em = MagicMock()
        mock_ep = MagicMock()
        mock_query = MagicMock()

        mock_em.get_endpoint.return_value = mock_ep
        mock_ep.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.collect.return_value = mock_endpoint_data

        # Atributos do endpoint (usados em ep.Indicador, ep.Data, etc.)
        mock_ep.Indicador = "Indicador"
        mock_ep.IndicadorDetalhe = "IndicadorDetalhe"
        mock_ep.Data = "Data"
        mock_ep.DataReferencia = "DataReferencia"
        mock_ep.Mediana = "Mediana"
        mock_ep.Media = "Media"
        mock_ep.DesvioPadrao = "DesvioPadrao"
        mock_ep.Minimo = "Minimo"
        mock_ep.Maximo = "Maximo"
        mock_ep.numeroRespondentes = "numeroRespondentes"
        mock_ep.baseCalculo = "baseCalculo"
        mock_ep.Suavizada = "Suavizada"

        return mock_em

    def test_get_focus_ipca_retorna_colunas_corretas(self, fetcher: BCBFetcher) -> None:
        """get_focus_ipca() deve retornar DataFrame com colunas snake_case."""
        mock_em = self._setup_focus_mock(_make_focus_df())

        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_ipca()

        expected_cols = {
            "data",
            "indicador",
            "indicador_detalhe",
            "ano_alvo",
            "mediana",
            "media",
            "desvio_padrao",
            "minimo",
            "maximo",
            "respondentes",
            "base_calculo",
        }
        assert set(result.columns) == expected_cols
        assert len(result) == 2
        assert result["mediana"].iloc[0] == 4.0

    def test_get_focus_selic_retorna_dataframe(self, fetcher: BCBFetcher) -> None:
        """get_focus_selic() deve retornar DataFrame não-vazio."""
        focus_df = _make_focus_df().copy()
        focus_df["Indicador"] = "Selic"
        mock_em = self._setup_focus_mock(focus_df)

        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_selic()

        assert not result.empty

    def test_get_focus_pib_retorna_dataframe(self, fetcher: BCBFetcher) -> None:
        mock_em = self._setup_focus_mock(_make_focus_df())
        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_pib()
        assert not result.empty

    def test_get_focus_cambio_retorna_dataframe(self, fetcher: BCBFetcher) -> None:
        mock_em = self._setup_focus_mock(_make_focus_df())
        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_cambio()
        assert not result.empty

    def test_get_focus_igpm_retorna_dataframe(self, fetcher: BCBFetcher) -> None:
        mock_em = self._setup_focus_mock(_make_focus_df())
        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_igpm()
        assert not result.empty

    def test_get_focus_data_e_datetime(self, fetcher: BCBFetcher) -> None:
        """Coluna 'data' deve ser dtype datetime64."""
        mock_em = self._setup_focus_mock(_make_focus_df())
        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_ipca()
        assert pd.api.types.is_datetime64_any_dtype(result["data"])

    def test_get_focus_vazio_retorna_dataframe_vazio(self, fetcher: BCBFetcher) -> None:
        """Quando API retorna vazio, deve retornar DataFrame vazio."""
        mock_em = self._setup_focus_mock(pd.DataFrame())
        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_ipca()
        assert result.empty

    def test_get_focus_ipca12m_retorna_colunas_corretas(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_focus_ipca12m() deve retornar DataFrame com campo 'suavizada'."""
        mock_em = self._setup_focus_mock(_make_focus_ipca12m_df())

        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_ipca12m()

        assert "suavizada" in result.columns
        assert "ano_alvo" not in result.columns  # Sem DataReferencia neste endpoint
        assert len(result) == 2

    def test_get_focus_all_retorna_dict_com_todos_indicadores(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_focus_all() deve retornar dict com chave para cada indicador."""
        mock_em = self._setup_focus_mock(_make_focus_df())
        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_all()

        assert isinstance(result, dict)
        for indicator in constants.BCB_FOCUS_INDICATORS_ANUAIS:
            assert indicator in result

    def test_get_focus_all_falha_individual_nao_propaga(
        self, fetcher: BCBFetcher
    ) -> None:
        """Falha em um indicador do Focus não deve propagar para os demais."""
        call_count = 0

        def side_effect_factory(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise ConnectionError("API timeout")
            return _make_focus_df()

        mock_em = MagicMock()
        mock_ep = MagicMock()
        mock_query = MagicMock()
        mock_em.get_endpoint.return_value = mock_ep
        mock_ep.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.collect.side_effect = side_effect_factory
        for attr in (
            "Indicador",
            "Data",
            "DataReferencia",
            "IndicadorDetalhe",
            "Mediana",
            "Media",
            "DesvioPadrao",
            "Minimo",
            "Maximo",
            "numeroRespondentes",
            "baseCalculo",
        ):
            setattr(mock_ep, attr, attr)

        with patch("bcb.Expectativas", return_value=mock_em):
            result = fetcher.get_focus_all()

        # Todos os indicadores devem estar no resultado (com DataFrame vazio nos que falharam)
        assert set(result.keys()) == set(constants.BCB_FOCUS_INDICATORS_ANUAIS)


# ============================================================================
# SEÇÃO 9: PTAX — CÂMBIO OFICIAL
# ============================================================================


class TestPTAX:
    """Testa os métodos PTAX via bcb.PTAX."""

    def _setup_ptax_mock(
        self,
        periodo_df: pd.DataFrame | None = None,
        moedas_df: pd.DataFrame | None = None,
        dia_df: pd.DataFrame | None = None,
    ):
        """Monta mock do OData endpoint PTAX."""
        mock_ptax_instance = MagicMock()
        mock_ep_periodo = MagicMock()
        mock_ep_moedas = MagicMock()
        mock_ep_dia = MagicMock()

        def get_endpoint_side_effect(name):
            if name == "CotacaoMoedaPeriodo":
                return mock_ep_periodo
            elif name == "Moedas":
                return mock_ep_moedas
            elif name == "CotacaoMoedaDia":
                return mock_ep_dia
            return MagicMock()

        mock_ptax_instance.get_endpoint.side_effect = get_endpoint_side_effect

        # Período endpoint
        mock_q_periodo = MagicMock()
        mock_ep_periodo.query.return_value = mock_q_periodo
        mock_q_periodo.parameters.return_value = mock_q_periodo
        mock_q_periodo.filter.return_value = mock_q_periodo
        mock_q_periodo.select.return_value = mock_q_periodo
        mock_q_periodo.collect.return_value = (
            _make_ptax_df() if periodo_df is None else periodo_df
        )
        mock_ep_periodo.tipoBoletim = "tipoBoletim"
        mock_ep_periodo.cotacaoCompra = "cotacaoCompra"
        mock_ep_periodo.cotacaoVenda = "cotacaoVenda"
        mock_ep_periodo.dataHoraCotacao = "dataHoraCotacao"

        # Moedas endpoint
        mock_q_moedas = MagicMock()
        mock_ep_moedas.query.return_value = mock_q_moedas
        mock_q_moedas.collect.return_value = (
            _make_ptax_moedas_df() if moedas_df is None else moedas_df
        )

        # Dia endpoint
        mock_q_dia = MagicMock()
        mock_ep_dia.query.return_value = mock_q_dia
        mock_q_dia.parameters.return_value = mock_q_dia
        mock_q_dia.filter.return_value = mock_q_dia
        mock_q_dia.select.return_value = mock_q_dia
        mock_q_dia.collect.return_value = dia_df or _make_ptax_dia_df()
        mock_ep_dia.tipoBoletim = "tipoBoletim"
        mock_ep_dia.cotacaoCompra = "cotacaoCompra"
        mock_ep_dia.cotacaoVenda = "cotacaoVenda"

        return mock_ptax_instance

    def test_get_ptax_currency_usd_retorna_colunas_corretas(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_ptax_currency('USD') deve retornar DataFrame com ['data','compra','venda','moeda']."""
        mock_ptax = self._setup_ptax_mock()

        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_ptax_currency("USD")

        assert list(result.columns) == ["data", "compra", "venda", "moeda", "fonte"]
        assert (result["moeda"] == "USD").all()
        assert (result["fonte"] == "bcb_ptax").all()
        assert len(result) == 3

    def test_get_ptax_currency_normaliza_para_maiusculo(
        self, fetcher: BCBFetcher
    ) -> None:
        """currency_code deve ser normalizado para maiúsculas automaticamente."""
        mock_ptax = self._setup_ptax_mock()

        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_ptax_currency("eur")

        assert (result["moeda"] == "EUR").all()
        assert "fonte" in result.columns

    def test_get_ptax_currency_date_e_datetime_normalizado(
        self, fetcher: BCBFetcher
    ) -> None:
        """Coluna 'data' deve ser datetime64 sem componente de hora."""
        mock_ptax = self._setup_ptax_mock()
        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_ptax_currency("USD")
        assert pd.api.types.is_datetime64_any_dtype(result["data"])
        # Normalizado: sem hora (00:00:00)
        assert (result["data"].dt.hour == 0).all()

    def test_get_ptax_currency_vazio_retorna_dataframe_vazio(
        self, fetcher: BCBFetcher
    ) -> None:
        """Quando BCB retorna vazio, deve retornar DataFrame com colunas esperadas."""
        mock_ptax = self._setup_ptax_mock(periodo_df=pd.DataFrame())
        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_ptax_currency("USD")
        assert result.empty
        assert list(result.columns) == ["data", "compra", "venda", "moeda", "fonte"]

    def test_get_ptax_all_currencies_retorna_todas_moedas(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_ptax_all_currencies() deve retornar DataFrame com todas as moedas listadas."""
        mock_ptax = self._setup_ptax_mock()
        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_ptax_all_currencies(date(2024, 1, 3))

        assert list(result.columns) == ["simbolo", "nome", "compra", "venda", "data"]
        assert len(result) == 3  # USD, EUR, GBP

    def test_get_available_currencies_retorna_dataframe(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_available_currencies() deve retornar DataFrame com moedas do BCB."""
        mock_ptax = self._setup_ptax_mock()
        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_available_currencies()

        assert list(result.columns) == ["simbolo", "nome", "tipo_moeda"]
        assert len(result) == 3
        assert "USD" in result["simbolo"].values

    def test_get_available_currencies_fallback_quando_vazio(
        self, fetcher: BCBFetcher
    ) -> None:
        """Quando Moedas endpoint retorna vazio, deve retornar lista padrão."""
        mock_ptax = self._setup_ptax_mock(moedas_df=pd.DataFrame())
        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_available_currencies()

        assert not result.empty
        assert "USD" in result["simbolo"].values

    def test_get_ptax_currency_moeda_suportada_usa_bcb(
        self, fetcher: BCBFetcher
    ) -> None:
        """Moedas suportadas pelo BCB (USD, EUR…) devem usar fonte 'bcb_ptax'."""
        mock_ptax = self._setup_ptax_mock()
        with patch("bcb.PTAX", return_value=mock_ptax):
            result = fetcher.get_ptax_currency("USD")
        assert (result["fonte"] == "bcb_ptax").all()

    def test_get_ptax_currency_moeda_nao_suportada_retorna_vazio(
        self, fetcher: BCBFetcher
    ) -> None:
        """Moeda não suportada pelo BCB (CNY) retorna DataFrame vazio sem chamar API.

        Fallback para Yahoo Finance é responsabilidade dos IngestNodes
        via fetch_with_fallback() — não do BCBFetcher.
        """
        result = fetcher.get_ptax_currency("CNY")

        assert result.empty
        assert list(result.columns) == ["data", "compra", "venda", "moeda", "fonte"]

    def test_get_ptax_currency_bcb_falha_retorna_vazio(
        self, fetcher: BCBFetcher
    ) -> None:
        """Quando BCB PTAX lança exceção, retorna DataFrame vazio (sem fallback Yahoo)."""
        with patch("bcb.PTAX", side_effect=Exception("BCB offline")):
            result = fetcher.get_ptax_currency("EUR")

        assert result.empty
        assert list(result.columns) == ["data", "compra", "venda", "moeda", "fonte"]

    def test_get_ptax_currency_ars_nao_suportada(self, fetcher: BCBFetcher) -> None:
        """ARS (peso argentino) não é suportada pelo BCB PTAX — retorna vazio."""
        result = fetcher.get_ptax_currency("ARS")

        assert result.empty
        assert list(result.columns) == ["data", "compra", "venda", "moeda", "fonte"]


# ============================================================================
# SEÇÃO 10: TAXAS DE CRÉDITO
# ============================================================================


class TestTaxaJuros:
    """Testa os métodos TaxaJuros via bcb.TaxaJuros."""

    def _setup_tj_mock(
        self,
        tj_df: pd.DataFrame | None = None,
        params_df: pd.DataFrame | None = None,
    ):
        """Monta mock do OData endpoint TaxaJuros."""
        mock_tj_instance = MagicMock()
        mock_ep_mensal = MagicMock()
        mock_ep_params = MagicMock()

        def get_endpoint_side_effect(name):
            if name == "TaxasJurosMensalPorMes":
                return mock_ep_mensal
            elif name == "ParametrosConsulta":
                return mock_ep_params
            return MagicMock()

        mock_tj_instance.get_endpoint.side_effect = get_endpoint_side_effect

        # TaxasJurosMensalPorMes endpoint
        mock_q = MagicMock()
        mock_ep_mensal.query.return_value = mock_q
        mock_q.filter.return_value = mock_q
        mock_q.collect.return_value = (
            tj_df if tj_df is not None else _make_taxa_juros_df()
        )
        mock_ep_mensal.Mes = "Mes"
        mock_ep_mensal.Modalidade = "Modalidade"

        # ParametrosConsulta endpoint
        mock_q_params = MagicMock()
        mock_ep_params.query.return_value = mock_q_params
        mock_q_params.collect.return_value = (
            params_df if params_df is not None else _make_params_consulta_df()
        )

        return mock_tj_instance

    def test_get_lending_rates_sem_filtro_retorna_todas(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_lending_rates() sem modality deve retornar todas as modalidades."""
        mock_tj = self._setup_tj_mock()
        with patch("bcb.TaxaJuros", return_value=mock_tj):
            result = fetcher.get_lending_rates()

        assert not result.empty
        assert "modalidade" in result.columns
        assert "taxa_mes" in result.columns
        assert "taxa_ano" in result.columns

    def test_get_lending_rates_colunas_snake_case(self, fetcher: BCBFetcher) -> None:
        """get_lending_rates() deve normalizar colunas para snake_case."""
        mock_tj = self._setup_tj_mock()
        with patch("bcb.TaxaJuros", return_value=mock_tj):
            result = fetcher.get_lending_rates()

        expected = {
            "mes",
            "modalidade",
            "posicao",
            "instituicao",
            "taxa_mes",
            "taxa_ano",
            "cnpj8",
            "ano_mes",
        }
        assert expected.issubset(set(result.columns))

    def test_get_lending_rates_taxa_e_numerica(self, fetcher: BCBFetcher) -> None:
        """Colunas taxa_mes e taxa_ano devem ser numéricas."""
        mock_tj = self._setup_tj_mock()
        with patch("bcb.TaxaJuros", return_value=mock_tj):
            result = fetcher.get_lending_rates()

        assert pd.api.types.is_numeric_dtype(result["taxa_mes"])
        assert pd.api.types.is_numeric_dtype(result["taxa_ano"])

    def test_get_all_lending_rates_retorna_dict_por_modalidade(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_all_lending_rates() deve retornar dict {modalidade: DataFrame}."""
        mock_tj = self._setup_tj_mock()
        with patch("bcb.TaxaJuros", return_value=mock_tj):
            result = fetcher.get_all_lending_rates()

        assert isinstance(result, dict)
        assert "Cheque especial" in result
        assert "Crédito pessoal" in result
        # Cada value é DataFrame sem coluna 'modalidade' (removida ao agrupar)
        for df in result.values():
            assert isinstance(df, pd.DataFrame)

    def test_get_all_lending_rates_vazio_retorna_dict_vazio(
        self, fetcher: BCBFetcher
    ) -> None:
        """Quando API retorna vazio, deve retornar dict vazio."""
        mock_tj = self._setup_tj_mock(tj_df=pd.DataFrame())
        with patch("bcb.TaxaJuros", return_value=mock_tj):
            result = fetcher.get_all_lending_rates()
        assert result == {}

    def test_get_lending_rate_modalities_retorna_colunas_corretas(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_lending_rate_modalities() deve retornar colunas snake_case."""
        mock_tj = self._setup_tj_mock()
        with patch("bcb.TaxaJuros", return_value=mock_tj):
            result = fetcher.get_lending_rate_modalities()

        assert "modalidade" in result.columns
        assert "codigo_modalidade" in result.columns


# ============================================================================
# SEÇÃO 11: GENÉRICOS
# ============================================================================


class TestGenericos:
    """Testa métodos genéricos: get_indicator, get_all_indicators, get_latest_values."""

    def test_get_indicator_por_codigo_retorna_dataframe(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_indicator() deve aceitar código numérico e retornar DataFrame."""
        mock_df = _make_sgs_df([11.75, 11.75])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_indicator(432)

        assert list(result.columns) == ["data", "valor"]

    def test_get_all_indicators_retorna_dict_com_todas_series(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_all_indicators() deve retornar dict com todas as séries configuradas."""
        mock_df = _make_sgs_df([10.0])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_all_indicators()

        from carteira_auto.config.constants import constants

        for name in constants.BCB_SERIES_CODES:
            assert name in result

    def test_get_all_indicators_falha_individual_nao_propaga(
        self, fetcher: BCBFetcher
    ) -> None:
        """Falha em uma série não deve impedir busca das demais."""
        call_count = 0

        def sgs_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("timeout")
            return _make_sgs_df([10.0])

        with patch("bcb.sgs.get", side_effect=sgs_side_effect):
            with patch("requests.get") as mock_http:
                mock_resp = MagicMock()
                mock_resp.json.return_value = [{"data": "01/01/2024", "valor": "10.0"}]
                mock_resp.raise_for_status.return_value = None
                mock_http.return_value = mock_resp
                result = fetcher.get_all_indicators()

        assert isinstance(result, dict)

    def test_get_latest_values_retorna_dict_com_floats_ou_none(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_latest_values() deve retornar dict {nome: float | None}."""
        mock_df = _make_sgs_df([11.75])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_latest_values()

        assert isinstance(result, dict)
        for v in result.values():
            assert v is None or isinstance(v, float)

    def test_get_latest_values_dataframe_vazio_retorna_none(
        self, fetcher: BCBFetcher
    ) -> None:
        """Quando série retorna DataFrame vazio, latest_values deve ser None."""
        empty_df = pd.DataFrame(columns=["data", "valor"])

        with patch.object(fetcher, "_fetch_sgs_last", return_value=empty_df):
            result = fetcher.get_latest_values()

        for v in result.values():
            assert v is None


# ============================================================================
# TESTES SGS — MÉTODOS ADICIONAIS DO MÓDULO bcb/ (Sprint B.4)
# ============================================================================


class TestBCBSGSNovosMetodos:
    """Testes parametrizados para métodos SGS sem cobertura anterior.

    Todos os métodos SGS seguem o mesmo padrão: chamam _fetch_sgs_series()
    que por sua vez usa bcb.sgs.get() → DataFrame com index Date e coluna valor.
    """

    @pytest.mark.parametrize(
        "method_name",
        [
            # Inflação complementar
            "get_igpdi",
            "get_ipca15",
            "get_core_ipca_ex0",
            # Atividade econômica
            "get_capacity_utilization",
            "get_consumer_confidence",
            "get_formal_employment_balance",
            "get_hours_worked",
            "get_minimum_wage",
            "get_real_average_income",
            "get_real_wage_bill",
            "get_unemployment_rate",
            # Fiscal e externo
            "get_current_account",
            "get_external_debt",
            "get_fdi_net",
            "get_fx_flow",
            "get_terms_of_trade",
            # Crédito e monetário
            "get_banking_spread_pf",
            "get_credit_cost_pf",
            "get_default_rate_total",
            "get_default_rate_corporate",
            "get_default_rate_pf_15_90",
            "get_default_rate_pf_90_plus",
            "get_default_rate_credit_card",
            "get_household_debt_ratio",
            "get_household_debt_service",
            "get_monetary_base",
            "get_reserve_requirements",
            # Juros derivados
            "get_real_interest_rate",
        ],
    )
    def test_metodo_sgs_retorna_dataframe(
        self, fetcher: BCBFetcher, method_name: str
    ) -> None:
        """Cada método SGS retorna DataFrame com coluna 'valor' ao receber dados."""
        mock_df = _make_sgs_df([10.5, 11.0, 10.8])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = getattr(fetcher, method_name)()

        assert isinstance(result, pd.DataFrame)
        assert "valor" in result.columns
        assert len(result) > 0

    @pytest.mark.parametrize(
        "method_name",
        [
            "get_igpdi",
            "get_ipca15",
            "get_unemployment_rate",
            "get_monetary_base",
        ],
    )
    def test_metodo_sgs_dataframe_vazio_retorna_vazio(
        self, fetcher: BCBFetcher, method_name: str
    ) -> None:
        """SGS com DataFrame vazio retorna DataFrame vazio (sem exceção)."""
        empty_df = pd.DataFrame(columns=["valor"])
        empty_df.index.name = "Date"
        with patch("bcb.sgs.get", return_value=empty_df):
            result = getattr(fetcher, method_name)()

        assert isinstance(result, pd.DataFrame)

    def test_get_ipca_expectation_12m_retorna_dataframe(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_ipca_expectation_12m usa SGS 13522 (expectativa IPCA 12m)."""
        mock_df = _make_sgs_df([4.5, 4.4, 4.3])
        with patch("bcb.sgs.get", return_value=mock_df):
            result = fetcher.get_ipca_expectation_12m()

        assert isinstance(result, pd.DataFrame)
        assert "valor" in result.columns


# ============================================================================
# TESTES FOCUS — MÉTODOS ADICIONAIS (Sprint B.4)
# ============================================================================


class TestBCBFocusNovosMetodos:
    """Testes para métodos Focus sem cobertura anterior."""

    # -- Métodos Focus sem argumento obrigatório --

    @pytest.mark.parametrize(
        "method_name,mock_method",
        [
            ("get_focus_selic_copom", "_fetch_focus_selic_copom"),
        ],
    )
    def test_focus_sem_args_retorna_dataframe(
        self, fetcher: BCBFetcher, method_name: str, mock_method: str
    ) -> None:
        """Métodos Focus sem argumento obrigatório retornam DataFrame."""
        mock_df = _make_focus_df()
        with patch.object(fetcher, mock_method, return_value=mock_df):
            result = getattr(fetcher, method_name)()

        assert isinstance(result, pd.DataFrame)

    def test_focus_ipca24m_retorna_dataframe(self, fetcher: BCBFetcher) -> None:
        """get_focus_ipca24m usa _fetch_focus_inflacao com suavizada='N'."""
        mock_df = _make_focus_ipca12m_df()
        with patch.object(fetcher, "_fetch_focus_inflacao", return_value=mock_df):
            result = fetcher.get_focus_ipca24m()

        assert isinstance(result, pd.DataFrame)

    # -- Métodos Focus com indicator obrigatório --

    @pytest.mark.parametrize(
        "method_name,mock_method",
        [
            ("get_focus_monthly", "_fetch_focus_mensais"),
            ("get_focus_quarterly", "_fetch_focus_trimestrais"),
        ],
    )
    def test_focus_com_indicator_retorna_dataframe(
        self, fetcher: BCBFetcher, method_name: str, mock_method: str
    ) -> None:
        """Métodos Focus com indicator obrigatório retornam DataFrame."""
        mock_df = _make_focus_df()
        with patch.object(fetcher, mock_method, return_value=mock_df):
            result = getattr(fetcher, method_name)("IPCA")

        assert isinstance(result, pd.DataFrame)

    # -- Métodos Focus Top5 --

    @pytest.mark.parametrize(
        "method_name,mock_method",
        [
            ("get_focus_top5", "_fetch_focus_top5_anuais"),
            ("get_focus_top5_selic", "_fetch_focus_top5_selic"),
            ("get_focus_top5_ipca12m", "_fetch_focus_top5_inflacao"),
            ("get_focus_top5_ipca24m", "_fetch_focus_top5_inflacao"),
        ],
    )
    def test_focus_top5_retorna_dataframe(
        self, fetcher: BCBFetcher, method_name: str, mock_method: str
    ) -> None:
        """Métodos Focus Top5 retornam DataFrame."""
        mock_df = _make_focus_df()
        with patch.object(fetcher, mock_method, return_value=mock_df):
            # get_focus_top5 requer indicator, os demais não
            if method_name == "get_focus_top5":
                result = getattr(fetcher, method_name)("IPCA")
            else:
                result = getattr(fetcher, method_name)()

        assert isinstance(result, pd.DataFrame)

    # -- Métodos Focus Top5 com indicator obrigatório --

    @pytest.mark.parametrize(
        "method_name",
        [
            "get_focus_top5_monthly",
            "get_focus_top5_quarterly",
        ],
    )
    def test_focus_top5_com_indicator_retorna_dataframe(
        self, fetcher: BCBFetcher, method_name: str
    ) -> None:
        """Focus Top5 com indicator obrigatório retorna DataFrame."""
        mock_df = _make_focus_df()
        with patch.object(fetcher, "_fetch_focus_generic_top5", return_value=mock_df):
            result = getattr(fetcher, method_name)("IPCA")

        assert isinstance(result, pd.DataFrame)

    # -- Métodos Focus batch (all) --

    @pytest.mark.parametrize(
        "method_name",
        [
            "get_focus_monthly_all",
            "get_focus_quarterly_all",
            "get_focus_top5_all",
        ],
    )
    def test_focus_batch_retorna_dict(
        self, fetcher: BCBFetcher, method_name: str
    ) -> None:
        """Métodos Focus batch (all) retornam dict {indicador: DataFrame}."""
        mock_df = _make_focus_df()
        with patch.object(
            fetcher, "_fetch_focus_batch", return_value={"IPCA": mock_df}
        ):
            result = getattr(fetcher, method_name)()

        assert isinstance(result, dict)

    def test_get_focus_reference_dates_retorna_dataframe(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_focus_reference_dates retorna DataFrame com datas de referência."""
        mock_df = pd.DataFrame(
            {
                "DataReferencia": ["2024-01-01", "2024-04-01"],
                "Tipo": ["Anual", "Anual"],
            }
        )
        with patch.object(
            fetcher, "_fetch_focus_reference_dates", return_value=mock_df
        ):
            result = fetcher.get_focus_reference_dates()

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# TESTES TAXAJUROS — MÉTODOS ADICIONAIS (Sprint B.4)
# ============================================================================


class TestBCBTaxaJurosNovosMetodos:
    """Testes para métodos TaxaJuros sem cobertura anterior."""

    def test_get_lending_rates_daily_retorna_dataframe(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_lending_rates_daily retorna DataFrame com taxas diárias."""
        mock_df = pd.DataFrame(
            {
                "InicioPeriodo": ["2024-01-01"],
                "FimPeriodo": ["2024-01-31"],
                "Modalidade": ["Cheque especial"],
                "Posicao": [1],
                "InstituicaoFinanceira": ["Banco X"],
                "TaxaJurosAoMes": [8.5],
                "TaxaJurosAoAno": [167.0],
            }
        )
        with patch.object(fetcher, "_fetch_lending_rates_odata", return_value=mock_df):
            result = fetcher.get_lending_rates_daily()

        assert isinstance(result, pd.DataFrame)

    def test_get_lending_rates_unified_retorna_dataframe(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_lending_rates_unified retorna DataFrame consolidado."""
        mock_df = _make_taxa_juros_df()
        with patch.object(fetcher, "_fetch_lending_rates_odata", return_value=mock_df):
            result = fetcher.get_lending_rates_unified()

        assert isinstance(result, pd.DataFrame)

    def test_get_lending_rate_dates_retorna_dataframe(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_lending_rate_dates retorna DataFrame com datas disponíveis."""
        mock_df = pd.DataFrame(
            {
                "InicioPeriodo": ["2024-01-01", "2024-02-01"],
                "FimPeriodo": ["2024-01-31", "2024-02-29"],
            }
        )
        with patch.object(fetcher, "_fetch_lending_rates_odata", return_value=mock_df):
            result = fetcher.get_lending_rate_dates()

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# TESTES MERCADO IMOBILIÁRIO (Sprint B.4 — novo mixin)
# ============================================================================


def _make_mercado_imobiliario_df(indicator_info: str = "indices_ivg") -> pd.DataFrame:
    """Cria DataFrame no formato retornado por bcb.MercadoImobiliario OData."""
    return pd.DataFrame(
        {
            "Data": pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"]),
            "Info": [indicator_info] * 3,
            "Valor": [150.5, 151.2, 152.0],
        }
    )


class TestBCBMercadoImobiliario:
    """Testes para BCBMercadoImobiliarioMixin — indicadores imobiliários OData."""

    @pytest.mark.parametrize(
        "method_name,indicator_key",
        [
            # Índices
            ("get_ivg", "ivg"),
            ("get_mvg", "mvg"),
            # Crédito PF — estoque
            ("get_credito_imobiliario_sfh", "credito_pf_sfh_total"),
            ("get_credito_imobiliario_fgts", "credito_pf_fgts_total"),
            ("get_credito_imobiliario_livre", "credito_pf_livre_total"),
            # Inadimplência
            ("get_inadimplencia_imobiliaria_sfh", "inadimplencia_pf_sfh_total"),
            ("get_inadimplencia_imobiliaria_livre", "inadimplencia_pf_livre_total"),
            # Taxas
            ("get_taxa_credito_imobiliario_sfh", "taxa_credito_pf_sfh_total"),
            ("get_taxa_credito_imobiliario_livre", "taxa_credito_pf_livre_total"),
            # Contratações
            ("get_contratacao_imobiliaria_sfh", "contratacao_pf_sfh_total"),
            ("get_contratacao_imobiliaria_livre", "contratacao_pf_livre_total"),
            # Imóveis
            ("get_imoveis_apartamento", "imoveis_tipo_apartamento_total"),
            ("get_imoveis_casa", "imoveis_tipo_casa_total"),
            ("get_imoveis_valor_medio", "imoveis_valor_medio_total"),
        ],
    )
    def test_metodo_imobiliario_retorna_dataframe(
        self, fetcher: BCBFetcher, method_name: str, indicator_key: str
    ) -> None:
        """Cada método imobiliário retorna DataFrame com colunas padrão."""
        # Mock no método interno — evita complexidade do OData mock
        mock_result = pd.DataFrame(
            {
                "data": pd.to_datetime(["2024-01-31", "2024-02-29"]),
                "valor": [150.5, 151.2],
                "indicador": [indicator_key, indicator_key],
            }
        )
        with patch.object(
            fetcher, "_fetch_mercado_imobiliario", return_value=mock_result
        ):
            result = getattr(fetcher, method_name)()

        assert isinstance(result, pd.DataFrame)
        assert "data" in result.columns
        assert "valor" in result.columns
        assert "indicador" in result.columns
        assert len(result) > 0

    def test_indicador_inexistente_retorna_vazio(self, fetcher: BCBFetcher) -> None:
        """_fetch_mercado_imobiliario com chave inválida retorna DataFrame vazio."""
        result = fetcher._fetch_mercado_imobiliario("chave_inexistente", 12)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_api_vazia_retorna_dataframe_vazio(self, fetcher: BCBFetcher) -> None:
        """Quando _fetch retorna DataFrame vazio, método retorna vazio."""
        empty = pd.DataFrame(columns=["data", "valor", "indicador"])
        with patch.object(fetcher, "_fetch_mercado_imobiliario", return_value=empty):
            result = fetcher.get_ivg()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_get_mercado_imobiliario_all_retorna_dict(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_mercado_imobiliario_all retorna dict com indicadores."""
        mock_df = _make_mercado_imobiliario_df("indices_ivg")
        with patch.object(fetcher, "_fetch_mercado_imobiliario", return_value=mock_df):
            result = fetcher.get_mercado_imobiliario_all()

        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_mercado_imobiliario_all_tolera_erros_parciais(
        self, fetcher: BCBFetcher
    ) -> None:
        """get_mercado_imobiliario_all continua mesmo se alguns indicadores falham."""
        call_count = 0

        def mock_fetch(indicator_key: str, period: int) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise ConnectionError("Erro simulado")
            return _make_mercado_imobiliario_df()

        with patch.object(
            fetcher, "_fetch_mercado_imobiliario", side_effect=mock_fetch
        ):
            result = fetcher.get_mercado_imobiliario_all()

        assert isinstance(result, dict)
        # Pelo menos alguns indicadores devem ter sido obtidos
        assert len(result) > 0
