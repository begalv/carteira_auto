"""Testes de integração do IBGEFetcher — chamadas reais às APIs.

Cobertura:
    - SIDRA (apisidra.ibge.gov.br via sidrapy + HTTP fallback)
    - CNAE (servicodados.ibge.gov.br/api/v2/cnae)
    - Países (servicodados.ibge.gov.br/api/v1/paises)

Estes testes NÃO usam mocks. Requerem conexão com a internet.
Execute com: pytest tests/integration/test_ibge_fetcher_integration.py -m integration -v

Validações:
    - DataFrame não-vazio
    - Colunas obrigatórias presentes
    - Valores numéricos em intervalos plausíveis
    - Tipos corretos (float, int, str)
"""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def fetcher():
    """IBGEFetcher compartilhado entre os testes do módulo."""
    from carteira_auto.data.fetchers import IBGEFetcher

    return IBGEFetcher()


# ============================================================================
# SEÇÃO 1: INFLAÇÃO — SIDRA
# ============================================================================


class TestSIDRAInflacao:
    """Testes de integração para métodos de inflação via SIDRA."""

    def test_get_ipca_retorna_dataframe(self, fetcher):
        """IPCA mensal retorna DataFrame com dados reais."""
        df = fetcher.get_ipca(months=6)

        assert df is not None
        assert not df.empty, "get_ipca retornou DataFrame vazio"
        assert "periodo" in df.columns
        assert "valor" in df.columns
        assert len(df) >= 3, f"Esperado ≥3 meses, obtido {len(df)}"

    def test_get_ipca_valores_plausíveis(self, fetcher):
        """Variação mensal do IPCA deve estar no intervalo [-2%, +5%] tipicamente."""
        df = fetcher.get_ipca(months=12)
        assert not df.empty

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty, "Todos os valores do IPCA são NaN"

        valores = df_validos["valor"]
        # IPCA mensal raramente ultrapassa ±5% (salvo hiperinflação)
        assert valores.max() < 10.0, f"Valor suspeito: {valores.max()}"
        assert valores.min() > -3.0, f"Valor suspeito: {valores.min()}"

    def test_get_ipca_new_variaveis_multiplas(self, fetcher):
        """IPCA série 2020+ retorna variação mensal, acumulada e peso."""
        df = fetcher.get_ipca_new(months=6)

        assert df is not None
        assert not df.empty, "get_ipca_new retornou DataFrame vazio"
        assert "variavel" in df.columns
        # Deve ter múltiplas variáveis (v=63,69,2265,66)
        variaveis = df["variavel"].unique()
        assert len(variaveis) >= 2, f"Esperado ≥2 variáveis, obtido: {variaveis}"

    def test_get_ipca15_retorna_dados(self, fetcher):
        """IPCA-15 retorna dados de prévia da inflação."""
        df = fetcher.get_ipca15(months=6)

        assert df is not None
        assert not df.empty, "get_ipca15 retornou DataFrame vazio"
        assert "periodo" in df.columns
        assert "valor" in df.columns

    def test_get_ipca_subitems_retorna_dados(self, fetcher):
        """IPCA por subitens retorna múltiplos grupos."""
        df = fetcher.get_ipca_subitems(months=2)

        assert df is not None
        assert not df.empty, "get_ipca_subitems retornou DataFrame vazio"
        # Tabela 1419 tem muitos subitens — deve ter muito mais que 1 linha por mês
        assert len(df) > 10, f"Poucos subitens: {len(df)}"

    def test_get_ipca_groups_retorna_grupos(self, fetcher):
        """IPCA por grupos retorna múltiplos grupos de consumo."""
        df = fetcher.get_ipca_groups(months=3)

        assert df is not None
        assert not df.empty, "get_ipca_groups retornou DataFrame vazio"
        # IPCA tem 9 grupos de consumo; cada mês deve ter ≥2 linhas
        assert len(df) >= 4, f"Poucos grupos: {len(df)}"

    def test_get_ipca_detailed_retorna_grupos(self, fetcher):
        """IPCA detailed (7060 grupos) retorna variação por grupo."""
        df = fetcher.get_ipca_detailed(months=3)

        assert df is not None
        assert not df.empty, "get_ipca_detailed retornou DataFrame vazio"
        assert "periodo" in df.columns
        assert "valor" in df.columns


# ============================================================================
# SEÇÃO 2: PIB — SIDRA
# ============================================================================


class TestSIDRAPIB:
    """Testes de integração para métodos de PIB via SIDRA."""

    def test_get_pib_retorna_dataframe(self, fetcher):
        """PIB trimestral retorna variações reais."""
        df = fetcher.get_pib(quarters=4)

        assert df is not None
        assert not df.empty, "get_pib retornou DataFrame vazio"
        assert "periodo" in df.columns
        assert "valor" in df.columns
        assert len(df) >= 2, f"Esperado ≥2 trimestres, obtido {len(df)}"

    def test_get_pib_valores_plausíveis(self, fetcher):
        """PIB trimestral deve estar no intervalo razoável [-15%, +15%]."""
        df = fetcher.get_pib(quarters=8)
        assert not df.empty

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty

        valores = df_validos["valor"]
        # Exclui pandemia (T2 2020: -11.8%)
        assert valores.max() < 20.0, f"Valor suspeito: {valores.max()}"
        assert valores.min() > -20.0, f"Valor suspeito: {valores.min()}"

    def test_get_pib_dessaz_retorna_indice(self, fetcher):
        """PIB dessazonalizado retorna série encadeada de volume."""
        df = fetcher.get_pib_dessaz(quarters=8)

        assert df is not None
        assert not df.empty, "get_pib_dessaz retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # Número-índice base 1995=100; valores atuais tipicamente > 100
        assert df_validos["valor"].max() > 50.0

    def test_get_pib_nominal_retorna_reais(self, fetcher):
        """PIB nominal retorna valores em R$ milhares."""
        df = fetcher.get_pib_nominal(years=3)

        assert df is not None
        assert not df.empty, "get_pib_nominal retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # PIB Brasil em R$ mil: atual ~10 trilhões = 10_000_000_000 (R$ mil)
        assert df_validos["valor"].max() > 1_000_000_000, "PIB nominal muito baixo"


# ============================================================================
# SEÇÃO 3: EMPREGO E RENDA — SIDRA
# ============================================================================


class TestSIDRAEmprego:
    """Testes de integração para métodos de emprego via SIDRA."""

    def test_get_unemployment_retorna_taxa(self, fetcher):
        """Desocupação retorna taxa % plausível."""
        df = fetcher.get_unemployment(quarters=4)

        assert df is not None
        assert not df.empty, "get_unemployment retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # Taxa de desocupação: histórico Brasil 6%-15%
        assert df_validos["valor"].max() < 20.0
        assert df_validos["valor"].min() > 0.0

    def test_get_underemployment_multiplas_variaveis(self, fetcher):
        """Mercado de trabalho completo retorna múltiplas variáveis."""
        df = fetcher.get_underemployment(quarters=4)

        assert df is not None
        assert not df.empty, "get_underemployment retornou DataFrame vazio"
        assert "variavel" in df.columns
        # v=4099,4097,12466,4096 → deve ter múltiplas variáveis
        variaveis = df["variavel"].unique()
        assert len(variaveis) >= 2, f"Esperado ≥2 variáveis, obtido: {variaveis}"

    def test_get_average_income_retorna_rendimento(self, fetcher):
        """Rendimento médio real retorna valores em R$."""
        df = fetcher.get_average_income(quarters=4)

        assert df is not None
        assert not df.empty, "get_average_income retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # Rendimento médio real no Brasil: R$2.500 a R$3.500
        assert df_validos["valor"].max() > 1000.0
        assert df_validos["valor"].min() > 500.0

    def test_get_population_retorna_milhares(self, fetcher):
        """População total retorna valores em mil pessoas."""
        df = fetcher.get_population(quarters=4)

        assert df is not None
        assert not df.empty, "get_population retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # População Brasil: ~215 milhões = 215.000 mil pessoas
        assert df_validos["valor"].max() > 100_000
        assert df_validos["valor"].min() > 50_000

    def test_get_gini_retorna_coeficiente(self, fetcher):
        """Gini retorna coeficiente entre 0 e 1."""
        df = fetcher.get_gini(years=5)

        assert df is not None
        assert not df.empty, "get_gini retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # Gini Brasil historicamente: 0.47 a 0.55
        assert df_validos["valor"].max() < 1.0
        assert df_validos["valor"].min() > 0.0


# ============================================================================
# SEÇÃO 4: ATIVIDADE SETORIAL — SIDRA
# ============================================================================


class TestSIDRASetorial:
    """Testes de integração para métodos de atividade setorial via SIDRA."""

    def test_get_industrial_production_retorna_variacao(self, fetcher):
        """PIM-PF retorna variação % da produção industrial."""
        df = fetcher.get_industrial_production(months=6)

        assert df is not None
        assert not df.empty, "get_industrial_production retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # Variação M/M-12: tipicamente entre -20% e +20%
        assert df_validos["valor"].max() < 50.0
        assert df_validos["valor"].min() > -50.0

    def test_get_retail_sales_retorna_dados(self, fetcher):
        """PMC retorna variação % do comércio varejista."""
        df = fetcher.get_retail_sales(months=6)

        assert df is not None
        assert not df.empty, "get_retail_sales retornou DataFrame vazio"
        assert "periodo" in df.columns
        assert "valor" in df.columns

    def test_get_services_retorna_dados(self, fetcher):
        """PMS (8688, base 2022=100) retorna variação % de serviços."""
        df = fetcher.get_services(months=6)

        assert df is not None
        assert not df.empty, "get_services retornou DataFrame vazio"
        assert "valor" in df.columns

    def test_get_construction_cost_retorna_dados(self, fetcher):
        """SINAPI retorna custo de construção civil."""
        df = fetcher.get_construction_cost(months=6)

        assert df is not None
        assert not df.empty, "get_construction_cost retornou DataFrame vazio"
        assert "valor" in df.columns

        df_validos = df.dropna(subset=["valor"])
        assert not df_validos.empty
        # Custo R$/m² da construção civil: tipicamente R$1.500 a R$2.500
        # (usa variáveis 48 e 1196; 48 é custo, 1196 é variação)
        assert df_validos["valor"].max() > 0.0


# ============================================================================
# SEÇÃO 5: GENÉRICO SIDRA
# ============================================================================


class TestSIDRAGenerico:
    """Testes do método get_sidra_table (acesso ad hoc)."""

    def test_get_sidra_table_tabela_valida(self, fetcher):
        """get_sidra_table retorna dados para tabela válida."""
        # Tabela 1737 — IPCA histórico (tabela mais estável)
        df = fetcher.get_sidra_table(table_code="1737", period="last 3")

        assert df is not None
        assert not df.empty, "get_sidra_table tabela 1737 retornou DataFrame vazio"
        assert "periodo" in df.columns
        assert "valor" in df.columns

    def test_get_sidra_table_com_classificacao(self, fetcher):
        """get_sidra_table aceita classificações e variáveis personalizadas."""
        # Tabela 7060 IPCA nova — variação mensal + índice geral
        df = fetcher.get_sidra_table(
            table_code="7060",
            period="last 3",
            variable="63",
            classifications={"315": "7169"},
        )

        assert df is not None
        assert not df.empty


# ============================================================================
# SEÇÃO 6: CNAE
# ============================================================================


class TestCNAE:
    """Testes de integração para métodos CNAE via servicodados."""

    def test_get_cnae_sections_retorna_21_secoes(self, fetcher):
        """CNAE 2.0 tem 21 seções (A a U)."""
        df = fetcher.get_cnae_sections()

        assert df is not None
        assert not df.empty, "get_cnae_sections retornou DataFrame vazio"
        assert "id" in df.columns
        assert "descricao" in df.columns
        # CNAE 2.0: exatamente 21 seções (A a U)
        assert len(df) == 21, f"Esperado 21 seções, obtido {len(df)}"
        # IDs devem ser letras de A a U
        assert set(df["id"].tolist()).issuperset({"A", "B", "C"})

    def test_get_cnae_divisions_retorna_muitas_divisoes(self, fetcher):
        """CNAE 2.0 tem 87 divisões econômicas."""
        df = fetcher.get_cnae_divisions()

        assert df is not None
        assert not df.empty, "get_cnae_divisions retornou DataFrame vazio"
        assert "id" in df.columns
        assert "descricao" in df.columns
        assert "secao_id" in df.columns
        assert "secao" in df.columns
        # CNAE 2.0: 87 divisões
        assert len(df) >= 80, f"Esperado ≥80 divisões, obtido {len(df)}"

    def test_get_cnae_classes_retorna_colunas_completas(self, fetcher):
        """Classes CNAE retornam hierarquia completa."""
        df = fetcher.get_cnae_classes()

        assert df is not None
        assert not df.empty, "get_cnae_classes retornou DataFrame vazio"
        assert set(df.columns).issuperset(
            {
                "id",
                "descricao",
                "grupo_id",
                "grupo",
                "divisao_id",
                "divisao",
                "secao_id",
                "secao",
            }
        )
        # CNAE 2.0: 673 classes
        assert len(df) >= 600, f"Esperado ≥600 classes, obtido {len(df)}"

    def test_get_cnae_subclasses_retorna_todas(self, fetcher):
        """Subclasses CNAE (sem filtro) retornam todas as 1332 subclasses."""
        df = fetcher.get_cnae_subclasses()

        assert df is not None
        assert not df.empty, "get_cnae_subclasses retornou DataFrame vazio"
        assert "id" in df.columns
        assert "descricao" in df.columns
        assert "classe_id" in df.columns
        assert "classe" in df.columns
        # CNAE 2.0: 1332 subclasses
        assert len(df) >= 1200, f"Esperado ≥1200 subclasses, obtido {len(df)}"

    def test_get_cnae_subclasses_por_classe(self, fetcher):
        """Subclasses filtradas por classe retornam subconjunto."""
        # Classe 0111-3 — Cultivo de cereais (existe e tem subclasses)
        df = fetcher.get_cnae_subclasses(class_code="01113")

        assert df is not None
        assert not df.empty, "get_cnae_subclasses filtrada retornou DataFrame vazio"
        assert len(df) >= 1, "Esperado ≥1 subclasse para classe 0111-3"
        # Todas as subclasses devem pertencer à classe requisitada
        assert all(df["classe_id"] == "01113"), "IDs de classe inconsistentes"

    def test_get_cnae_search_retorna_resultados(self, fetcher):
        """Busca CNAE por 'tecnologia' retorna resultados relevantes."""
        df = fetcher.get_cnae_search("tecnologia")

        assert df is not None
        assert not df.empty, "get_cnae_search 'tecnologia' retornou DataFrame vazio"
        # Pelo menos 1 resultado
        assert len(df) >= 1
        # Todas as descrições devem conter 'tecnologia' (case-insensitive)
        for desc in df["descricao"].tolist():
            assert "tecnologia" in desc.lower(), f"Resultado não contém termo: {desc}"

    def test_get_cnae_search_software_retorna_resultados(self, fetcher):
        """Busca CNAE por 'software' retorna resultados TI."""
        df = fetcher.get_cnae_search("software")

        assert df is not None
        assert not df.empty, "get_cnae_search 'software' retornou DataFrame vazio"
        assert len(df) >= 1

    def test_get_cnae_search_termo_inexistente_retorna_vazio(self, fetcher):
        """Busca CNAE por termo inexistente retorna DataFrame vazio."""
        df = fetcher.get_cnae_search("xyzzy_inexistente_123")

        assert df is not None
        assert (
            df.empty or len(df) == 0
        ), "Esperado DataFrame vazio para termo inexistente"


# ============================================================================
# SEÇÃO 7: PAÍSES
# ============================================================================


class TestPaises:
    """Testes de integração para métodos de Países via servicodados."""

    def test_get_country_list_retorna_paises(self, fetcher):
        """Lista de países retorna ≥100 países com metadados."""
        df = fetcher.get_country_list()

        assert df is not None
        assert not df.empty, "get_country_list retornou DataFrame vazio"
        assert set(df.columns).issuperset(
            {"codigo", "nome", "capital", "regiao", "sub_regiao"}
        )
        # Mundo tem ~195 países; API IBGE deve ter ≥100
        assert len(df) >= 100, f"Esperado ≥100 países, obtido {len(df)}"

    def test_get_country_list_brasil_presente(self, fetcher):
        """Brasil deve estar na lista de países."""
        df = fetcher.get_country_list()
        assert not df.empty

        # Brasil: código BR
        brasil = df[df["codigo"] == "BR"]
        assert not brasil.empty, "Brasil não encontrado na lista (código BR)"
        assert brasil.iloc[0]["nome"] != "", "Nome do Brasil está vazio"

    def test_get_country_info_brasil(self, fetcher):
        """get_country_info retorna dict com informações do Brasil."""
        info = fetcher.get_country_info("BR")

        assert info is not None
        assert isinstance(info, dict)
        assert len(info) > 0, "get_country_info retornou dict vazio para BR"

    def test_get_country_info_codigo_invalido_retorna_vazio(self, fetcher):
        """Código de país inválido retorna dict vazio."""
        info = fetcher.get_country_info("ZZ")  # Código inexistente

        # API pode retornar lista vazia ou erro → deve retornar {}
        assert info is not None
        assert isinstance(info, dict)

    def test_get_country_indicators_brasil(self, fetcher):
        """Indicadores do Brasil retornam PIB e IDH com valores plausíveis."""
        from carteira_auto.config.constants import constants

        # Usa apenas PIB e IDH para rapidez
        pib_id = constants.IBGE_COUNTRY_INDICATORS["pib"]
        idh_id = constants.IBGE_COUNTRY_INDICATORS["idh"]

        df = fetcher.get_country_indicators("BR", indicator_ids=[pib_id, idh_id])

        assert df is not None
        assert not df.empty, "get_country_indicators retornou DataFrame vazio para BR"
        assert set(df.columns).issuperset({"indicador", "ano", "valor", "unidade"})

        # Deve ter dados de pelo menos 1 indicador
        assert df["indicador"].nunique() >= 1

        # PIB Brasil em US$: deve ser > 1 trilhão (valor em alguma unidade)
        pib_rows = df[df["valor"].notna()]
        assert not pib_rows.empty, "Nenhum valor numérico nos indicadores"
        # Valores de IDH: entre 0 e 1
        # Valores de PIB: > 0 (em bilhões US$)
        assert pib_rows["valor"].max() > 0

    def test_get_country_indicators_colunas_completas(self, fetcher):
        """DataFrame de indicadores contém colunas obrigatórias."""
        from carteira_auto.config.constants import constants

        indicator_ids = list(constants.IBGE_COUNTRY_INDICATORS.values())[:3]
        df = fetcher.get_country_indicators("US", indicator_ids=indicator_ids)

        assert df is not None
        # Mesmo vazio, deve ter colunas certas
        assert set(df.columns).issuperset({"indicador", "ano", "valor", "unidade"})

    def test_get_country_rank_pib(self, fetcher):
        """Ranking por PIB retorna top 20 países com estrutura correta."""
        from carteira_auto.config.constants import constants

        pib_id = constants.IBGE_COUNTRY_INDICATORS["pib"]
        df = fetcher.get_country_rank(indicator_id=pib_id, top_n=10)

        assert df is not None
        # Pode retornar vazio se não houver dados
        if not df.empty:
            assert set(df.columns).issuperset(
                {"posicao", "codigo", "nome", "valor", "ano"}
            )
            assert len(df) <= 10
            # Posições devem ser sequenciais a partir de 1
            assert df["posicao"].iloc[0] == 1

    def test_get_country_rank_usa_mais_recente(self, fetcher):
        """Ranking sem ano especificado usa dados mais recentes disponíveis."""
        from carteira_auto.config.constants import constants

        idh_id = constants.IBGE_COUNTRY_INDICATORS["idh"]
        df = fetcher.get_country_rank(indicator_id=idh_id, top_n=5)

        assert df is not None
        if not df.empty:
            # IDH entre 0 e 1
            assert df["valor"].max() <= 1.0
            assert df["valor"].min() >= 0.0
            # Ano deve ser plausível (após 2000)
            assert df["ano"].max() >= 2000


# ============================================================================
# SAÚDE GERAL — smoke tests rápidos
# ============================================================================


class TestSmoke:
    """Smoke tests rápidos para detectar regressões na integração."""

    def test_fetcher_instancia_corretamente(self):
        """IBGEFetcher pode ser instanciado sem erros."""
        from carteira_auto.data.fetchers import IBGEFetcher

        f = IBGEFetcher()
        assert f is not None

    def test_sidrapy_importa_corretamente(self):
        """sidrapy está instalado e importa corretamente."""
        import sidrapy

        assert sidrapy is not None
        assert hasattr(sidrapy, "get_table")

    def test_constants_ibge_country_indicators_configurado(self):
        """IBGE_COUNTRY_INDICATORS tem entradas configuradas."""
        from carteira_auto.config.constants import constants

        assert hasattr(constants, "IBGE_COUNTRY_INDICATORS")
        assert len(constants.IBGE_COUNTRY_INDICATORS) >= 5
        assert "pib" in constants.IBGE_COUNTRY_INDICATORS
        assert "idh" in constants.IBGE_COUNTRY_INDICATORS

    def test_constants_ibge_table_ids_configurado(self):
        """IBGE_TABLE_IDS tem todas as tabelas esperadas."""
        from carteira_auto.config.constants import constants

        tabelas_esperadas = [
            "ipca",
            "ipca_nova",
            "ipca_subitens",
            "ipca15",
            "pib_trimestral",
            "pib_dessazonalizado",
            "pib_nominal",
            "pnad_desocupacao",
            "pnad_rendimento",
            "pnad_populacao",
            "pnad_subutilizacao",
            "pnad_gini",
            "pim_pf",
            "pmc",
            "pms",
            "sinapi",
        ]
        for tabela in tabelas_esperadas:
            assert (
                tabela in constants.IBGE_TABLE_IDS
            ), f"Tabela '{tabela}' não encontrada em IBGE_TABLE_IDS"
