"""Fetcher do IBGE — SIDRA, CNAE e Países.

Motor interno SIDRA: sidrapy.get_table() (primário) → HTTP raw (fallback).

APIs utilizadas:
    - SIDRA (apisidra.ibge.gov.br): tabelas de pesquisas IBGE via sidrapy
    - CNAE (servicodados.ibge.gov.br/api/v2/cnae): classificação econômica
    - Países (servicodados.ibge.gov.br/api/v1/paises): indicadores internacionais

SIDRA — tabelas utilizadas (19):
    Inflação:   1737 (IPCA hist.), 7060 (IPCA 2020+), 1419 (subitens), 7062 (IPCA-15)
    PIB:        5932 (trim. var%), 1621 (dessaz. índice), 5938 (nominal R$)
    Emprego:    6381 (desocupação), 6387 (rendimento), 4093 (merc. trabalho),
                6022 (população), 7453 (Gini)
    Setorial:   8888 (PIM-PF), 8881 (PMC), 8688 (PMS), 2296 (SINAPI)
    Educação:   7113 (analfabetismo)

API SIDRA: https://apisidra.ibge.gov.br/values/t/{tabela}/...
Sem autenticação. Limite: 100.000 valores por consulta.

Endpoints OData adicionais:
    CNAE: https://servicodados.ibge.gov.br/api/v2/cnae (secoes, divisoes, classes, subclasses)
    Países: https://servicodados.ibge.gov.br/api/v1/paises (indicadores anuais em US$)
"""

import ssl

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from carteira_auto.config import settings
from carteira_auto.config.constants import constants
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
    rate_limit,
    retry,
)

logger = get_logger(__name__)

# Base URLs para as APIs do servicodados.ibge.gov.br
_CNAE_BASE_URL = "https://servicodados.ibge.gov.br/api/v2/cnae"
_PAISES_BASE_URL = "https://servicodados.ibge.gov.br/api/v1/paises"


class _IBGESSLAdapter(HTTPAdapter):
    """Adapter HTTP com SSL legacy para o servidor SIDRA do IBGE.

    O servidor apisidra.ibge.gov.br requer OP_LEGACY_SERVER_CONNECT
    para negociação SSL. O sidrapy resolve isso internamente; este adapter
    replica o workaround para o fallback HTTP raw.
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class IBGEFetcher:
    """Fetcher para dados do IBGE via SIDRA, CNAE e Países.

    Motor SIDRA: sidrapy.get_table() (primário) → HTTP raw (fallback).
    APIs CNAE e Países: HTTP direto (servicodados.ibge.gov.br).
    """

    def __init__(self) -> None:
        self._base_url = settings.ibge.BASE_URL
        self._timeout = settings.ibge.TIMEOUT
        self._tables = constants.IBGE_TABLE_IDS

    # =========================================================================
    # SEÇÃO 1: INFLAÇÃO (SIDRA)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca(self, months: int = 12) -> pd.DataFrame:
        """IPCA — variação mensal (%) | Mensal (~9 dias após fim do mês) | Tabela 1737.

        Args:
            months: Número de meses a buscar (cada período = 1 mês).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = variação % mensal (ex: 0.52 = 0,52%).
            Para acumulado anual: ((1 + valor/100).prod() - 1) * 100
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["ipca"]),
            variable="63",  # Variação mensal
            period=f"last {months}",
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca_detailed(self, months: int = 12) -> pd.DataFrame:
        """IPCA por grupos de produtos — variação mensal (%) | Mensal | Tabela 7060.

        Desagregação por grupos: Alimentação, Habitação, Transportes, Saúde,
        Comunicação, Despesas pessoais, Vestuário, Educação.

        Args:
            months: Número de meses a buscar (cada período = 1 mês).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel', 'grupo'].
            valor = variação % mensal por grupo.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["ipca_nova"]),
            variable="63",  # Variação mensal
            period=f"last {months}",
            classifications={"315": "7170,7445,7486,7558,7625,7660,7712,7766,7786"},
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca_new(self, months: int = 12) -> pd.DataFrame:
        """IPCA série 2020+ — variação mensal, acumulada e peso | Tabela 7060.

        Inclui variação mensal (v=63), acum. ano (v=69), acum. 12m (v=2265)
        e peso mensal (v=66) para o índice geral.

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["ipca_nova"]),
            variable="63,69,2265,66",
            period=f"last {months}",
            classifications={"315": "7169"},  # Índice geral
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca_subitems(self, months: int = 6) -> pd.DataFrame:
        """IPCA por subitens — variação mensal (%) | Tabela 1419 (jan/2012 a dez/2019).

        Desagregação detalhada por 464 subitens do IPCA.

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel', 'grupo'].
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["ipca_subitens"]),
            variable="63",
            period=f"last {months}",
            classifications={"315": "allxt"},  # Todos exceto total
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca15(self, months: int = 12) -> pd.DataFrame:
        """IPCA-15 (prévia da inflação) — variação mensal (%) | Tabela 7062.

        Divulgado ~15 dias antes do IPCA cheio. Indicador antecedente.

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["ipca15"]),
            variable="355",  # Variação mensal IPCA-15
            period=f"last {months}",
            classifications={"315": "7169"},  # Índice geral
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_ipca_groups(self, months: int = 12) -> pd.DataFrame:
        """IPCA — variação mensal + peso por grupos | Tabela 7060.

        Retorna variação (v=63) e peso (v=66) para cada grupo do IPCA.
        Útil para análise de composição da inflação.

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel', 'grupo'].
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["ipca_nova"]),
            variable="63,66",  # Variação mensal + peso
            period=f"last {months}",
            classifications={"315": "7170,7445,7486,7558,7625,7660,7712,7766,7786"},
        )

    # =========================================================================
    # SEÇÃO 2: PIB (SIDRA)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_pib(self, quarters: int = 8) -> pd.DataFrame:
        """PIB trimestral — variação % vs mesmo trimestre do ano anterior | Tabela 5932.

        Args:
            quarters: Número de trimestres a buscar (cada período = 1 trimestre).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = variação % em relação ao mesmo trimestre do ano anterior.
            Exemplo: 2.3 = PIB cresceu 2,3% vs mesmo trimestre do ano anterior.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pib_trimestral"]),
            variable="6561",  # Taxa variação % vs mesmo período ano anterior
            period=f"last {quarters}",
            classifications={"11255": "90707"},  # PIB total (evita "..")
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_pib_dessaz(self, quarters: int = 20) -> pd.DataFrame:
        """PIB dessazonalizado — série encadeada de volume (base 1995=100) | Tabela 1621.

        Útil para análise de tendência do PIB sem efeitos sazonais.

        Args:
            quarters: Número de trimestres a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = número-índice (base média 1995 = 100).
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pib_dessazonalizado"]),
            variable="584",  # Série encadeada com ajuste sazonal
            period=f"last {quarters}",
            classifications={"11255": "90707"},  # PIB a preços de mercado
        )

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_pib_nominal(self, years: int = 5) -> pd.DataFrame:
        """PIB a preços correntes — R$ milhares | Tabela 5938 (anual, municipal).

        Dados anuais agregados. Usando nível Brasil (n1/1).

        Args:
            years: Número de anos a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = R$ milhares.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pib_nominal"]),
            variable="37",  # PIB a preços correntes (Mil Reais)
            period=f"last {years}",
        )

    # =========================================================================
    # SEÇÃO 3: EMPREGO E RENDA (SIDRA)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_unemployment(self, quarters: int = 8) -> pd.DataFrame:
        """Taxa de desocupação — PNAD Contínua (%) | Trimestral | Tabela 6381.

        Cada período = 1 trimestre móvel (ex: jan-fev-mar, fev-mar-abr...).
        Reflete a média da taxa no trimestre, não um mês específico.

        Args:
            quarters: Número de trimestres a buscar (cada período = 1 tri. móvel).

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = taxa de desocupação % (ex: 8.2 = 8,2% da força de trabalho).
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pnad_desocupacao"]),
            variable="4099",  # Taxa de desocupação
            period=f"last {quarters}",
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_underemployment(self, quarters: int = 8) -> pd.DataFrame:
        """Mercado de trabalho completo — PNAD Contínua | Trimestral | Tabela 4093.

        Inclui: taxa de desocupação, nível de ocupação, informalidade,
        participação na força de trabalho.

        Args:
            quarters: Número de trimestres a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            Múltiplas variáveis por período (desocupação, informalidade, etc.).
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pnad_subutilizacao"]),
            variable="4099,4097,12466,4096",
            period=f"last {quarters}",
            classifications={"2": "6794"},  # Total (ambos os sexos)
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_average_income(self, quarters: int = 12) -> pd.DataFrame:
        """Rendimento médio real efetivamente recebido — PNAD | Tabela 6387.

        Trimestre móvel. Valor em R$ de rendimento médio real.

        Args:
            quarters: Número de trimestres a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = rendimento médio real efetivo em R$.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pnad_rendimento"]),
            variable="5935",  # Rendimento médio real efetivo
            period=f"last {quarters}",
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_population(self, quarters: int = 8) -> pd.DataFrame:
        """População total — PNAD Contínua (mil pessoas) | Tabela 6022.

        Trimestre móvel.

        Args:
            quarters: Número de trimestres a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = população em milhares de pessoas.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pnad_populacao"]),
            variable="606",  # População (Mil pessoas)
            period=f"last {quarters}",
        )

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_gini(self, years: int = 10) -> pd.DataFrame:
        """Índice de Gini do rendimento — PNAD Contínua anual | Tabela 7453.

        Mede desigualdade de renda (0 = igualdade, 1 = máxima desigualdade).

        Args:
            years: Número de anos a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = coeficiente de Gini (ex: 0.489).
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pnad_gini"]),
            variable="10806",  # Índice de Gini
            period=f"last {years}",
        )

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_analfabetismo(self, years: int = 10) -> pd.DataFrame:
        """Taxa de analfabetismo 15+ anos — PNAD Contínua anual | Tabela 7113.

        Percentual da população de 15 anos ou mais que não sabe ler e escrever.
        Indicador social relevante para análise de desenvolvimento econômico.

        Args:
            years: Número de anos a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = taxa de analfabetismo em % (ex: 5.6).
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["analfabetismo"]),
            variable="10267",  # Taxa de analfabetismo
            period=f"last {years}",
        )

    # =========================================================================
    # SEÇÃO 4: ATIVIDADE ECONÔMICA SETORIAL (SIDRA)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_industrial_production(self, months: int = 12) -> pd.DataFrame:
        """PIM-PF — variação % da produção industrial | Mensal | Tabela 8888.

        Índice base 2022=100.

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = variação % mês vs mesmo mês ano anterior (M/M-12).
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pim_pf"]),
            variable="11602",  # Variação M/M-12 (%)
            period=f"last {months}",
            classifications={"544": "129314"},  # Indústria geral
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_retail_sales(self, months: int = 12) -> pd.DataFrame:
        """PMC — variação % do comércio varejista ampliado | Mensal | Tabela 8881.

        Índice base 2022=100.

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = variação % volume de vendas M/M-12.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pmc"]),
            variable="11709",  # Variação M/M-12 (%)
            period=f"last {months}",
            classifications={"11046": "56736"},  # Volume vendas (não receita)
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_services(self, months: int = 12) -> pd.DataFrame:
        """PMS — variação % do volume de serviços | Mensal | Tabela 8688.

        Índice base 2022=100. Substitui tabela 8162 (encerrada dez/2022).

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = variação % volume de serviços M/M-12.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["pms"]),
            variable="11624",  # Variação M/M-12 (%)
            period=f"last {months}",
            classifications={
                "11046": "56726",  # Volume de serviços (não receita)
                "12355": "107071",  # Total
            },
        )

    @log_execution
    @cache_result(ttl_seconds=7200)
    def get_construction_cost(self, months: int = 12) -> pd.DataFrame:
        """SINAPI — custo da construção civil | Mensal | Tabela 2296.

        Custo médio por m² (R$) e variação % mensal.

        Args:
            months: Número de meses a buscar.

        Returns:
            DataFrame com colunas ['periodo', 'valor', 'variavel'].
            valor = custo R$/m² ou variação % conforme variável.
        """
        return self._fetch_sidra_table(
            table_code=str(self._tables["sinapi"]),
            variable="48,1196",  # Custo R$/m² + variação % no mês
            period=f"last {months}",
        )

    # =========================================================================
    # SEÇÃO 5: GENÉRICO SIDRA
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_sidra_table(
        self,
        table_code: str | int,
        territorial_level: str = "1",
        period: str = "last 12",
        variable: str | None = None,
        classifications: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """Acesso direto a qualquer tabela do SIDRA.

        Permite consultas ad hoc a qualquer tabela IBGE sem necessidade
        de um método específico.

        Args:
            table_code: Código da tabela (ex: "1737", 7060).
            territorial_level: Nível territorial (default: "1" = Brasil).
            period: Períodos (ex: "last 12", "all", "202301,202302").
            variable: Códigos de variáveis (ex: "63,69"). None = allxp.
            classifications: Dict {classificação: categorias}
                             (ex: {"315": "7169"}).

        Returns:
            DataFrame normalizado ['periodo', 'valor', 'variavel', ...].
        """
        return self._fetch_sidra_table(
            table_code=str(table_code),
            variable=variable,
            period=period,
            territorial_level=territorial_level,
            classifications=classifications,
        )

    # =========================================================================
    # SEÇÃO 6: CNAE (servicodados.ibge.gov.br)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_cnae_sections(self) -> pd.DataFrame:
        """Seções CNAE 2.0 — 21 seções econômicas (A a U).

        Returns:
            DataFrame com colunas ['id', 'descricao'].
        """
        data = self._fetch_servicodados(f"{_CNAE_BASE_URL}/secoes")
        if not data:
            return pd.DataFrame(columns=["id", "descricao"])
        return pd.DataFrame(
            [{"id": r["id"], "descricao": r["descricao"]} for r in data]
        )

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_cnae_divisions(self) -> pd.DataFrame:
        """Divisões CNAE 2.0 — 87 divisões econômicas.

        Returns:
            DataFrame com colunas ['id', 'descricao', 'secao_id', 'secao'].
        """
        data = self._fetch_servicodados(f"{_CNAE_BASE_URL}/divisoes")
        if not data:
            return pd.DataFrame(columns=["id", "descricao", "secao_id", "secao"])
        rows = []
        for r in data:
            secao = r.get("secao", {})
            rows.append(
                {
                    "id": r["id"],
                    "descricao": r["descricao"],
                    "secao_id": secao.get("id", ""),
                    "secao": secao.get("descricao", ""),
                }
            )
        return pd.DataFrame(rows)

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_cnae_classes(self) -> pd.DataFrame:
        """Classes CNAE 2.0 — 673 classes com hierarquia completa.

        Returns:
            DataFrame com colunas ['id', 'descricao', 'grupo_id', 'grupo',
            'divisao_id', 'divisao', 'secao_id', 'secao'].
        """
        data = self._fetch_servicodados(f"{_CNAE_BASE_URL}/classes")
        if not data:
            return pd.DataFrame(
                columns=[
                    "id",
                    "descricao",
                    "grupo_id",
                    "grupo",
                    "divisao_id",
                    "divisao",
                    "secao_id",
                    "secao",
                ]
            )
        rows = []
        for r in data:
            grupo = r.get("grupo", {})
            divisao = grupo.get("divisao", {})
            secao = divisao.get("secao", {})
            rows.append(
                {
                    "id": r["id"],
                    "descricao": r["descricao"],
                    "grupo_id": grupo.get("id", ""),
                    "grupo": grupo.get("descricao", ""),
                    "divisao_id": divisao.get("id", ""),
                    "divisao": divisao.get("descricao", ""),
                    "secao_id": secao.get("id", ""),
                    "secao": secao.get("descricao", ""),
                }
            )
        return pd.DataFrame(rows)

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_cnae_subclasses(self, class_code: str | None = None) -> pd.DataFrame:
        """Subclasses CNAE 2.0 — nível mais detalhado (1332 subclasses).

        Args:
            class_code: Se informado, retorna subclasses de uma classe
                        específica (ex: "01113"). Se None, retorna todas.

        Returns:
            DataFrame com colunas ['id', 'descricao', 'classe_id', 'classe'].
        """
        if class_code:
            url = f"{_CNAE_BASE_URL}/classes/{class_code}/subclasses"
        else:
            url = f"{_CNAE_BASE_URL}/subclasses"
        data = self._fetch_servicodados(url)
        if not data:
            return pd.DataFrame(columns=["id", "descricao", "classe_id", "classe"])
        rows = []
        for r in data:
            classe = r.get("classe", {})
            rows.append(
                {
                    "id": r["id"],
                    "descricao": r["descricao"],
                    "classe_id": classe.get("id", ""),
                    "classe": classe.get("descricao", ""),
                }
            )
        return pd.DataFrame(rows)

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_cnae_search(self, term: str) -> pd.DataFrame:
        """Busca subclasses CNAE por termo na descrição (filtro client-side).

        A API CNAE não suporta busca server-side — carrega todas as
        subclasses e filtra localmente por substring case-insensitive.

        Args:
            term: Termo de busca (ex: "tecnologia", "software", "petróleo").

        Returns:
            DataFrame com colunas ['id', 'descricao', 'classe_id', 'classe'].
        """
        all_subclasses = self.get_cnae_subclasses()
        if all_subclasses.empty:
            return all_subclasses
        mask = all_subclasses["descricao"].str.contains(term, case=False, na=False)
        result = all_subclasses[mask].reset_index(drop=True)
        logger.debug(f"CNAE busca '{term}': {len(result)} resultados")
        return result

    # =========================================================================
    # SEÇÃO 7: PAÍSES (servicodados.ibge.gov.br)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_country_list(self) -> pd.DataFrame:
        """Lista todos os países com metadados básicos.

        Returns:
            DataFrame com colunas ['codigo', 'nome', 'capital', 'regiao',
            'sub_regiao', 'area_km2', 'moeda'].
        """
        data = self._fetch_servicodados(f"{_PAISES_BASE_URL}/todos")
        if not data:
            return pd.DataFrame(
                columns=[
                    "codigo",
                    "nome",
                    "capital",
                    "regiao",
                    "sub_regiao",
                    "area_km2",
                    "moeda",
                ]
            )
        rows = []
        for r in data:
            id_info = r.get("id", {})
            nome = r.get("nome", {})
            loc = r.get("localizacao", {})
            gov = r.get("governo", {})
            area = r.get("area", {})
            moedas = r.get("unidades-monetarias", [{}])
            rows.append(
                {
                    "codigo": id_info.get("ISO-3166-1-ALPHA-2", ""),
                    "nome": nome.get("abreviado", ""),
                    "capital": gov.get("capital", {}).get("nome", ""),
                    "regiao": loc.get("regiao", {}).get("nome", ""),
                    "sub_regiao": loc.get("sub-regiao", {}).get("nome", ""),
                    "area_km2": area.get("total", ""),
                    "moeda": moedas[0].get("nome", "") if moedas else "",
                }
            )
        return pd.DataFrame(rows)

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_country_info(self, country_code: str) -> dict:
        """Informações detalhadas de um país específico.

        Args:
            country_code: Código ISO Alpha-2 (ex: "BR", "US", "CN").

        Returns:
            Dict com metadados do país ou dict vazio se não encontrado.
        """
        data = self._fetch_servicodados(f"{_PAISES_BASE_URL}/{country_code}")
        if not data:
            return {}
        return data[0] if isinstance(data, list) and data else data

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_country_indicators(
        self,
        country_code: str,
        indicator_ids: list[int] | None = None,
    ) -> pd.DataFrame:
        """Indicadores econômicos e sociais de um país — séries anuais.

        Disponíveis: PIB, PIB per capita, IDH, exportações, importações,
        esperança de vida, gastos com educação/saúde, P&D, população.
        NÃO disponíveis: inflação, desemprego, dívida/PIB, Gini.

        Args:
            country_code: Código ISO Alpha-2 (ex: "BR", "US").
            indicator_ids: Lista de IDs de indicadores. Se None, busca todos
                           os configurados em IBGE_COUNTRY_INDICATORS.

        Returns:
            DataFrame com colunas ['indicador', 'ano', 'valor', 'unidade'].
            Valores convertidos para float quando possível.
        """
        if indicator_ids is None:
            indicator_ids = list(constants.IBGE_COUNTRY_INDICATORS.values())
        ids_str = "|".join(str(i) for i in indicator_ids)
        url = f"{_PAISES_BASE_URL}/{country_code}/indicadores/{ids_str}"
        data = self._fetch_servicodados(url)
        if not data:
            return pd.DataFrame(columns=["indicador", "ano", "valor", "unidade"])

        rows = []
        for indicator in data:
            # API Países usa "indicador" (não "nome") como campo de nome
            nome = indicator.get("indicador", "")
            unidade = indicator.get("unidade", {}).get("id", "")
            for series in indicator.get("series", []):
                # "serie" é lista de dicts de uma chave: [{"1990": "val"}, ...]
                # Inclui entradas nulas e períodos ("1990-1995") — filtrar.
                serie_list = series.get("serie", [])
                for item in serie_list:
                    for ano, valor in item.items():
                        if not ano.isdigit():  # pula "-", "1990-1995", etc.
                            continue
                        if valor is not None and valor != "":
                            rows.append(
                                {
                                    "indicador": nome,
                                    "ano": int(ano),
                                    "valor": pd.to_numeric(valor, errors="coerce"),
                                    "unidade": unidade,
                                }
                            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(["indicador", "ano"]).reset_index(drop=True)
        logger.debug(
            f"Países {country_code}: {len(df)} registros " f"de {len(data)} indicadores"
        )
        return df

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_country_rank(
        self,
        indicator_id: int,
        year: int | None = None,
        top_n: int = 20,
    ) -> pd.DataFrame:
        """Ranking de países por um indicador específico.

        Busca o indicador para todos os países e ordena decrescente.

        Args:
            indicator_id: ID do indicador (ex: 77827 = PIB).
                          Ver constants.IBGE_COUNTRY_INDICATORS.
            year: Ano específico. Se None, usa o mais recente disponível.
            top_n: Número de países no ranking (default: 20).

        Returns:
            DataFrame com colunas ['posicao', 'codigo', 'nome', 'valor', 'ano'].
        """
        empty = pd.DataFrame(columns=["posicao", "codigo", "nome", "valor", "ano"])
        countries = self.get_country_list()
        if countries.empty:
            return empty

        # Busca indicador para todos os países de uma vez
        codes = ",".join(countries["codigo"].dropna().tolist())
        url = f"{_PAISES_BASE_URL}/{codes}/indicadores/{indicator_id}"
        data = self._fetch_servicodados(url)
        if not data:
            return empty

        rows = []
        for indicator in data:
            for series in indicator.get("series", []):
                # API usa "pais" (não "localidade") para identificar o país
                pais = series.get("pais", {})
                codigo = pais.get("id", "")
                nome = pais.get("nome", "")
                # "serie" é lista de dicts de uma chave; converte para dict filtrado
                serie_list = series.get("serie", [])
                serie = {
                    k: v
                    for item in serie_list
                    for k, v in item.items()
                    if k.isdigit()  # apenas anos inteiros (não "-", "1990-1995")
                }

                valor = None
                ano_usado = year

                if year:
                    valor = serie.get(str(year))
                else:
                    # Pega o mais recente com valor não-nulo
                    for ano_str in sorted(serie.keys(), reverse=True):
                        v = serie[ano_str]
                        if v is not None and v != "":
                            valor = v
                            ano_usado = int(ano_str)
                            break

                if valor is not None and valor != "":
                    valor_num = pd.to_numeric(valor, errors="coerce")
                    if pd.notna(valor_num) and ano_usado is not None:
                        rows.append(
                            {
                                "codigo": codigo,
                                "nome": nome,
                                "valor": valor_num,
                                "ano": ano_usado,
                            }
                        )

        if not rows:
            return empty

        df = pd.DataFrame(rows).sort_values("valor", ascending=False).head(top_n)
        df["posicao"] = range(1, len(df) + 1)
        return df[["posicao", "codigo", "nome", "valor", "ano"]].reset_index(drop=True)

    # =========================================================================
    # INTERNOS — MOTOR SIDRA (sidrapy → HTTP fallback)
    # =========================================================================

    def _fetch_sidra_table(
        self,
        table_code: str,
        variable: str | None = None,
        period: str = "last 12",
        territorial_level: str = "1",
        classifications: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """Busca tabela SIDRA. Motor: sidrapy (primário) → HTTP (fallback)."""
        try:
            return self._fetch_via_sidrapy(
                table_code,
                variable,
                period,
                territorial_level,
                classifications,
            )
        except Exception as e:
            logger.warning(
                f"sidrapy falhou para tabela {table_code}: {e}. "
                "Usando fallback HTTP SIDRA."
            )
            return self._fetch_http(
                table_code,
                variable,
                period,
                territorial_level,
                classifications,
            )

    @retry(max_attempts=2, delay=0.5)
    def _fetch_via_sidrapy(
        self,
        table_code: str,
        variable: str | None,
        period: str,
        territorial_level: str,
        classifications: dict[str, str] | None,
    ) -> pd.DataFrame:
        """Busca via sidrapy.get_table() (motor primário).

        sidrapy resolve SSL legacy internamente. Tenta 2x antes de
        propagar exceção para o fallback HTTP.
        """
        import sidrapy

        kwargs: dict = {
            "table_code": table_code,
            "territorial_level": territorial_level,
            "ibge_territorial_code": "all",
            "period": period,
            "header": "n",
        }
        if variable:
            kwargs["variable"] = variable
        if classifications:
            kwargs["classifications"] = classifications

        logger.debug(f"sidrapy: tabela {table_code}, v={variable}, p={period}")
        df = sidrapy.get_table(**kwargs)

        if df is None or df.empty:
            logger.warning(f"sidrapy tabela {table_code}: sem dados")
            return pd.DataFrame(columns=["periodo", "valor", "variavel"])

        return self._normalize_sidra(df)

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_http(
        self,
        table_code: str,
        variable: str | None,
        period: str,
        territorial_level: str,
        classifications: dict[str, str] | None,
    ) -> pd.DataFrame:
        """Busca via HTTP raw com SSL legacy adapter (fallback).

        Replica a URL que o sidrapy constrói, com adapter SSL customizado.
        """
        # Constrói path SIDRA
        path = f"/t/{table_code}"
        path += f"/n{territorial_level}/all"
        path += "/h/n"
        path += f"/p/{period}"
        if variable:
            path += f"/v/{variable}"
        else:
            path += "/v/allxp"
        if classifications:
            for classif, cats in classifications.items():
                path += f"/c{classif}/{cats}"

        url = f"{self._base_url}{path}"
        logger.debug(f"IBGE HTTP SIDRA: {url}")

        session = requests.Session()
        session.mount("https://", _IBGESSLAdapter())

        response = session.get(
            url,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

        data = response.json()

        if not data:
            logger.warning(f"HTTP SIDRA: sem dados tabela {table_code}")
            return pd.DataFrame(columns=["periodo", "valor", "variavel"])

        df = pd.DataFrame(data)
        return self._normalize_sidra(df)

    @staticmethod
    def _normalize_sidra(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza DataFrame do SIDRA para schema padrão.

        Input: colunas SIDRA (D1C, D1N, D2C, D2N, D3N..., V, MN).
        Output: ['periodo', 'valor', 'variavel', ...] + 'grupo' se presente.
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=["periodo", "valor", "variavel"])

        result = pd.DataFrame()

        # Valor numérico — coluna V
        if "V" in df.columns:
            result["valor"] = pd.to_numeric(df["V"], errors="coerce")

        # Período — D1C (código) e D1N (nome legível)
        if "D1C" in df.columns:
            result["periodo_codigo"] = df["D1C"]
        if "D1N" in df.columns:
            result["periodo"] = df["D1N"]
        elif "D1C" in df.columns:
            result["periodo"] = df["D1C"]

        # Variável — D2N (nome descritivo)
        if "D2N" in df.columns:
            result["variavel"] = df["D2N"]

        # Classificações adicionais (grupos IPCA, setores, etc.)
        # D3N = classificação nível 3, D4N = nível 4 (hierárquicos)
        if "D3N" in df.columns:
            result["grupo"] = df["D3N"]
        if "D4N" in df.columns:
            # Se D3N já existe, D4N vai para coluna separada (subgrupo)
            col_name = "subgrupo" if "grupo" in result.columns else "grupo"
            result[col_name] = df["D4N"]

        # Unidade
        if "MN" in df.columns:
            result["unidade"] = df["MN"]

        # Remove linhas sem valor
        if "valor" in result.columns:
            result = result.dropna(subset=["valor"])

        logger.debug(f"SIDRA normalizado: {len(result)} registros")
        return result

    # =========================================================================
    # INTERNOS — HTTP PARA SERVICODADOS (CNAE, PAÍSES)
    # =========================================================================

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_servicodados(self, url: str) -> list | dict | None:
        """Busca dados de servicodados.ibge.gov.br (CNAE, Países).

        Retorna o JSON parsed (lista ou dict), ou None em caso de erro.
        """
        logger.debug(f"IBGE servicodados: {url}")
        try:
            response = requests.get(
                url,
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"IBGE servicodados falhou ({url}): {e}")
            return None
