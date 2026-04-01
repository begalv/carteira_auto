"""Testes do IBGEFetcher v2 — motor sidrapy + CNAE + Países.

Cobre:
    - Motor SIDRA: sidrapy.get_table() (primário) e fallback HTTP
    - Métodos existentes (backward compat): get_ipca, get_ipca_detailed, get_pib, get_unemployment
    - Novos métodos SIDRA: inflação, PIB, emprego, setorial
    - Genérico: get_sidra_table
    - CNAE: sections, divisions, classes, subclasses, search
    - Países: list, info, indicators, rank
    - Normalização SIDRA: colunas ['periodo', 'valor', 'variavel', 'grupo']
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from carteira_auto.data.fetchers.ibge_fetcher import IBGEFetcher

# ============================================================================
# FIXTURES E HELPERS
# ============================================================================


@pytest.fixture
def fetcher() -> IBGEFetcher:
    return IBGEFetcher()


def _make_sidra_df(
    values: list[float],
    periodos: list[str] | None = None,
    variavel: str = "IPCA - Variação mensal",
    grupo: str | None = None,
) -> pd.DataFrame:
    """Cria DataFrame no formato retornado por sidrapy.get_table(header='n')."""
    n = len(values)
    if periodos is None:
        periodos = [f"janeiro 202{i}" for i in range(n)]

    data = {
        "NC": ["Brasil"] * n,
        "NN": ["Brasil"] * n,
        "D1C": [f"20240{i + 1}" for i in range(n)],
        "D1N": periodos,
        "D2C": ["63"] * n,
        "D2N": [variavel] * n,
        "V": [str(v) for v in values],
        "MN": ["%"] * n,
    }
    if grupo:
        data["D3C"] = ["7170"] * n
        data["D3N"] = [grupo] * n
    return pd.DataFrame(data)


def _make_cnae_sections() -> list[dict]:
    return [
        {"id": "A", "descricao": "AGRICULTURA", "observacoes": []},
        {"id": "B", "descricao": "INDÚSTRIAS EXTRATIVAS", "observacoes": []},
        {"id": "C", "descricao": "INDÚSTRIAS DE TRANSFORMAÇÃO", "observacoes": []},
    ]


def _make_cnae_divisions() -> list[dict]:
    return [
        {
            "id": "01",
            "descricao": "AGRICULTURA E PECUÁRIA",
            "secao": {"id": "A", "descricao": "AGRICULTURA"},
            "observacoes": [],
        },
        {
            "id": "10",
            "descricao": "FABRICAÇÃO DE PRODUTOS ALIMENTÍCIOS",
            "secao": {"id": "C", "descricao": "INDÚSTRIAS DE TRANSFORMAÇÃO"},
            "observacoes": [],
        },
    ]


def _make_cnae_classes() -> list[dict]:
    return [
        {
            "id": "01113",
            "descricao": "CULTIVO DE CEREAIS",
            "grupo": {
                "id": "011",
                "descricao": "LAVOURAS TEMPORÁRIAS",
                "divisao": {
                    "id": "01",
                    "descricao": "AGRICULTURA",
                    "secao": {"id": "A", "descricao": "AGRICULTURA"},
                },
            },
            "observacoes": [],
        }
    ]


def _make_cnae_subclasses() -> list[dict]:
    return [
        {
            "id": "0111301",
            "descricao": "CULTIVO DE ARROZ",
            "classe": {"id": "01113", "descricao": "CULTIVO DE CEREAIS"},
            "atividades": [],
            "observacoes": [],
        },
        {
            "id": "6201501",
            "descricao": "DESENVOLVIMENTO DE SOFTWARE SOB ENCOMENDA",
            "classe": {"id": "62015", "descricao": "DESENVOLVIMENTO DE PROGRAMAS"},
            "atividades": [],
            "observacoes": [],
        },
    ]


def _make_country_list() -> list[dict]:
    return [
        {
            "id": {"ISO-3166-1-ALPHA-2": "BR", "M49": 76},
            "nome": {"abreviado": "Brasil"},
            "localizacao": {
                "regiao": {"nome": "America"},
                "sub-regiao": {"nome": "America do Sul"},
            },
            "governo": {"capital": {"nome": "Brasilia"}},
            "area": {"total": "8510345"},
            "unidades-monetarias": [{"nome": "Real brasileiro"}],
        },
        {
            "id": {"ISO-3166-1-ALPHA-2": "US", "M49": 840},
            "nome": {"abreviado": "Estados Unidos"},
            "localizacao": {
                "regiao": {"nome": "America"},
                "sub-regiao": {"nome": "America do Norte"},
            },
            "governo": {"capital": {"nome": "Washington D.C."}},
            "area": {"total": "9833520"},
            "unidades-monetarias": [{"nome": "Dolar americano"}],
        },
    ]


def _make_country_indicators() -> list[dict]:
    # Estrutura real da API Países: "indicador" (não "nome"), "pais" (não
    # "localidade"), "serie" é lista de dicts de uma chave (não dict direto).
    return [
        {
            "id": 77827,
            "indicador": "Total do PIB",
            "unidade": {"id": "US$", "multiplicador": 1},
            "series": [
                {
                    "pais": {"id": "BR", "nome": "Brasil"},
                    "serie": [
                        {"2022": "1920095687805.73"},
                        {"2023": "2173665655937.27"},
                    ],
                }
            ],
        }
    ]


def _make_country_rank_data() -> list[dict]:
    # Estrutura real: "indicador", "pais", "serie" como lista de dicts.
    return [
        {
            "id": 77827,
            "indicador": "Total do PIB",
            "unidade": {"id": "US$"},
            "series": [
                {
                    "pais": {"id": "US", "nome": "Estados Unidos"},
                    "serie": [{"2023": "25462700000000"}],
                },
                {
                    "pais": {"id": "BR", "nome": "Brasil"},
                    "serie": [{"2023": "2173665655937.27"}],
                },
                {
                    "pais": {"id": "AR", "nome": "Argentina"},
                    "serie": [{"2023": "641131000000"}],
                },
            ],
        }
    ]


# ============================================================================
# SEÇÃO 1-4: MÉTODOS SIDRA — motor sidrapy primário
# ============================================================================


class TestSIDRAPrimario:
    """Testa que os métodos SIDRA usam sidrapy como motor primário."""

    def test_get_ipca_retorna_colunas_corretas(self, fetcher: IBGEFetcher) -> None:
        """get_ipca() deve retornar DataFrame com colunas padrão SIDRA."""
        mock_df = _make_sidra_df([0.52, 0.48, 0.61])
        with patch("sidrapy.get_table", return_value=mock_df):
            result = fetcher.get_ipca(months=3)

        assert "periodo" in result.columns
        assert "valor" in result.columns
        assert "variavel" in result.columns
        assert len(result) == 3

    def test_get_ipca_detailed_tem_grupo(self, fetcher: IBGEFetcher) -> None:
        """get_ipca_detailed() deve retornar coluna 'grupo'."""
        mock_df = _make_sidra_df([0.30], grupo="Alimentação e bebidas")
        with patch("sidrapy.get_table", return_value=mock_df):
            result = fetcher.get_ipca_detailed(months=1)

        assert "grupo" in result.columns

    def test_get_pib_retorna_dataframe(self, fetcher: IBGEFetcher) -> None:
        """get_pib() deve retornar DataFrame não-vazio."""
        mock_df = _make_sidra_df([2.3, 1.8], variavel="PIB - taxa de variacao")
        with patch("sidrapy.get_table", return_value=mock_df):
            result = fetcher.get_pib(quarters=2)

        assert not result.empty
        assert result["valor"].iloc[0] == 2.3

    def test_get_unemployment_retorna_dataframe(self, fetcher: IBGEFetcher) -> None:
        """get_unemployment() deve retornar DataFrame não-vazio."""
        mock_df = _make_sidra_df([8.2, 7.9], variavel="Taxa de desocupacao")
        with patch("sidrapy.get_table", return_value=mock_df):
            result = fetcher.get_unemployment(quarters=2)

        assert not result.empty

    @pytest.mark.parametrize(
        "method_name",
        [
            "get_ipca_new",
            "get_ipca15",
            "get_ipca_groups",
            "get_pib_dessaz",
            "get_pib_nominal",
            "get_underemployment",
            "get_average_income",
            "get_population",
            "get_gini",
            "get_industrial_production",
            "get_retail_sales",
            "get_services",
            "get_construction_cost",
        ],
    )
    def test_novo_metodo_sidra_retorna_dataframe(
        self, fetcher: IBGEFetcher, method_name: str
    ) -> None:
        """Cada novo método SIDRA deve retornar DataFrame normalizado."""
        mock_df = _make_sidra_df([100.0, 101.0])
        with patch("sidrapy.get_table", return_value=mock_df):
            method = getattr(fetcher, method_name)
            # Métodos com arg obrigatório
            if method_name in ("get_ipca_subitems",):
                result = method(months=2)
            else:
                result = method()

        assert "periodo" in result.columns
        assert "valor" in result.columns
        assert len(result) == 2


class TestSIDRAFallbackHTTP:
    """Testa o fallback HTTP quando sidrapy falha."""

    def test_fallback_http_quando_sidrapy_falha(self, fetcher: IBGEFetcher) -> None:
        """Quando sidrapy falha, deve usar HTTP com SSL adapter."""
        http_response = [
            {
                "D1C": "202401",
                "D1N": "janeiro 2024",
                "D2C": "63",
                "D2N": "IPCA - Variação mensal",
                "V": "0.52",
                "MN": "%",
            }
        ]

        with patch("sidrapy.get_table", side_effect=Exception("sidrapy offline")):
            with patch("requests.Session") as mock_session_cls:
                mock_session = MagicMock()
                mock_response = MagicMock()
                mock_response.json.return_value = http_response
                mock_response.raise_for_status.return_value = None
                mock_session.get.return_value = mock_response
                mock_session_cls.return_value = mock_session

                result = fetcher.get_ipca(months=1)

        assert not result.empty
        assert result["valor"].iloc[0] == 0.52

    def test_sidrapy_vazio_retorna_dataframe_vazio(self, fetcher: IBGEFetcher) -> None:
        """Quando sidrapy retorna DataFrame vazio, resultado tem colunas corretas."""
        with patch("sidrapy.get_table", return_value=pd.DataFrame()):
            result = fetcher.get_ipca(months=1)

        assert result.empty
        assert "periodo" in result.columns
        assert "valor" in result.columns


class TestSIDRAGenerico:
    """Testa get_sidra_table (acesso genérico)."""

    def test_get_sidra_table_aceita_codigo_int(self, fetcher: IBGEFetcher) -> None:
        """get_sidra_table() deve aceitar table_code como int."""
        mock_df = _make_sidra_df([10.5])
        with patch("sidrapy.get_table", return_value=mock_df) as mock_get:
            result = fetcher.get_sidra_table(table_code=1737, period="last 1")

        assert not result.empty
        # Verifica que converteu int→str para sidrapy
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["table_code"] == "1737"

    def test_get_sidra_table_com_classificacoes(self, fetcher: IBGEFetcher) -> None:
        """get_sidra_table() deve passar classifications para sidrapy."""
        mock_df = _make_sidra_df([4.0], grupo="Alimentação")
        classif = {"315": "7170"}
        with patch("sidrapy.get_table", return_value=mock_df) as mock_get:
            fetcher.get_sidra_table(
                table_code="7060", variable="63", classifications=classif
            )

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["classifications"] == classif


# ============================================================================
# SEÇÃO 6: CNAE
# ============================================================================


class TestCNAE:
    """Testa métodos da API CNAE."""

    def test_get_cnae_sections_retorna_colunas(self, fetcher: IBGEFetcher) -> None:
        """get_cnae_sections() deve retornar DataFrame com ['id', 'descricao']."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_cnae_sections()):
            result = fetcher.get_cnae_sections()

        assert list(result.columns) == ["id", "descricao"]
        assert len(result) == 3

    def test_get_cnae_divisions_inclui_secao(self, fetcher: IBGEFetcher) -> None:
        """get_cnae_divisions() deve incluir secao_id e secao."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_cnae_divisions()):
            result = fetcher.get_cnae_divisions()

        assert "secao_id" in result.columns
        assert result["secao_id"].iloc[0] == "A"

    def test_get_cnae_classes_hierarquia_completa(self, fetcher: IBGEFetcher) -> None:
        """get_cnae_classes() deve incluir hierarquia grupo→divisão→seção."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_cnae_classes()):
            result = fetcher.get_cnae_classes()

        assert "grupo_id" in result.columns
        assert "divisao_id" in result.columns
        assert "secao_id" in result.columns

    def test_get_cnae_subclasses_por_classe(self, fetcher: IBGEFetcher) -> None:
        """get_cnae_subclasses(class_code) deve filtrar por classe."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_cnae_subclasses()[:1]) as mock:
            fetcher.get_cnae_subclasses(class_code="01113")

        # Verifica que a URL inclui o código da classe
        call_url = mock.call_args[0][0]
        assert "classes/01113/subclasses" in call_url

    def test_get_cnae_subclasses_todas(self, fetcher: IBGEFetcher) -> None:
        """get_cnae_subclasses() sem args deve buscar todas."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_cnae_subclasses()) as mock:
            result = fetcher.get_cnae_subclasses()

        call_url = mock.call_args[0][0]
        assert call_url.endswith("/subclasses")
        assert len(result) == 2

    def test_get_cnae_search_filtra_client_side(self, fetcher: IBGEFetcher) -> None:
        """get_cnae_search() deve filtrar por substring case-insensitive."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_cnae_subclasses()):
            result = fetcher.get_cnae_search("software")

        assert len(result) == 1
        assert "SOFTWARE" in result["descricao"].iloc[0]

    def test_get_cnae_search_vazio_retorna_vazio(self, fetcher: IBGEFetcher) -> None:
        """get_cnae_search() sem resultados deve retornar DataFrame vazio."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_cnae_subclasses()):
            result = fetcher.get_cnae_search("xyz_inexistente_abc")

        assert result.empty

    def test_get_cnae_api_indisponivel_retorna_vazio(
        self, fetcher: IBGEFetcher
    ) -> None:
        """Se API CNAE falhar, retorna DataFrame vazio com colunas corretas."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=None):
            result = fetcher.get_cnae_sections()

        assert result.empty
        assert list(result.columns) == ["id", "descricao"]


# ============================================================================
# SEÇÃO 7: PAÍSES
# ============================================================================


class TestPaises:
    """Testa métodos da API Países."""

    def test_get_country_list_retorna_colunas(self, fetcher: IBGEFetcher) -> None:
        """get_country_list() deve retornar DataFrame com metadados."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_country_list()):
            result = fetcher.get_country_list()

        assert "codigo" in result.columns
        assert "nome" in result.columns
        assert "capital" in result.columns
        assert len(result) == 2
        assert result["codigo"].iloc[0] == "BR"

    def test_get_country_info_retorna_dict(self, fetcher: IBGEFetcher) -> None:
        """get_country_info() deve retornar dict com metadados do país."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=[_make_country_list()[0]]):
            result = fetcher.get_country_info("BR")

        assert isinstance(result, dict)
        assert result["nome"]["abreviado"] == "Brasil"

    def test_get_country_indicators_retorna_series(self, fetcher: IBGEFetcher) -> None:
        """get_country_indicators() deve retornar séries anuais."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=_make_country_indicators()):
            result = fetcher.get_country_indicators("BR", [77827])

        assert list(result.columns) == ["indicador", "ano", "valor", "unidade"]
        assert len(result) == 2
        assert result["ano"].iloc[0] == 2022
        assert result["valor"].iloc[0] > 0

    def test_get_country_indicators_default_todos(self, fetcher: IBGEFetcher) -> None:
        """get_country_indicators() sem ids busca todos os configurados."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=[]) as mock:
            fetcher.get_country_indicators("BR")

        # Deve ter montado URL com todos os IDs
        call_url = mock.call_args[0][0]
        assert "77827" in call_url  # PIB
        assert "77823" in call_url  # PIB per capita

    def test_get_country_rank_ordena_decrescente(self, fetcher: IBGEFetcher) -> None:
        """get_country_rank() deve retornar ranking ordenado decrescente."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path) as mock:
            mock.side_effect = [
                _make_country_list(),  # get_country_list
                _make_country_rank_data(),  # ranking query
            ]
            result = fetcher.get_country_rank(indicator_id=77827, top_n=3)

        assert list(result.columns) == ["posicao", "codigo", "nome", "valor", "ano"]
        assert result["posicao"].iloc[0] == 1
        # EUA deve ser primeiro (maior PIB)
        assert result["codigo"].iloc[0] == "US"
        assert result["valor"].iloc[0] > result["valor"].iloc[1]

    def test_get_country_rank_com_ano_especifico(self, fetcher: IBGEFetcher) -> None:
        """get_country_rank() com year deve filtrar por ano específico."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path) as mock:
            mock.side_effect = [
                _make_country_list(),
                _make_country_rank_data(),
            ]
            result = fetcher.get_country_rank(indicator_id=77827, year=2023, top_n=3)

        assert not result.empty
        assert (result["ano"] == 2023).all()

    def test_get_country_api_indisponivel(self, fetcher: IBGEFetcher) -> None:
        """Se API Países falhar, retorna DataFrame vazio com colunas."""
        mock_path = (
            "carteira_auto.data.fetchers.ibge_fetcher."
            "IBGEFetcher._fetch_servicodados"
        )
        with patch(mock_path, return_value=None):
            result = fetcher.get_country_list()

        assert result.empty
        assert "codigo" in result.columns


# ============================================================================
# NORMALIZAÇÃO SIDRA
# ============================================================================


class TestNormalizacao:
    """Testa a normalização do formato SIDRA para schema padrão."""

    def test_normalize_converte_valor_para_numerico(self) -> None:
        """Coluna V (string) deve ser convertida para float."""
        df = _make_sidra_df([0.52, 0.48])
        result = IBGEFetcher._normalize_sidra(df)
        assert result["valor"].dtype in ("float64", "float32")

    def test_normalize_remove_valores_nulos(self) -> None:
        """Linhas com valor '..' ou não-numérico devem ser removidas."""
        df = _make_sidra_df([0.52])
        df.loc[1] = df.iloc[0].copy()
        df.at[1, "V"] = ".."
        result = IBGEFetcher._normalize_sidra(df)
        assert len(result) == 1

    def test_normalize_dataframe_vazio(self) -> None:
        """DataFrame vazio deve retornar DataFrame vazio com colunas padrão."""
        result = IBGEFetcher._normalize_sidra(pd.DataFrame())
        assert result.empty
        assert "periodo" in result.columns

    def test_normalize_preserva_grupo_quando_presente(self) -> None:
        """Coluna 'grupo' deve ser preservada quando D3N existe."""
        df = _make_sidra_df([0.30], grupo="Alimentação")
        result = IBGEFetcher._normalize_sidra(df)
        assert "grupo" in result.columns
        assert result["grupo"].iloc[0] == "Alimentação"
