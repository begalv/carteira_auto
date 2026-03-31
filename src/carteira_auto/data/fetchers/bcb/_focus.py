"""BCBFetcher — Focus (Expectativas de Mercado via bcb.Expectativas OData).

Cobertura: 13/13 endpoints disponíveis no serviço Expectativas do BCB.

Endpoints por tipo:
    Anuais:     ExpectativasMercadoAnuais, ExpectativasMercadoTop5Anuais
    Mensais:    ExpectativaMercadoMensais, ExpectativasMercadoTop5Mensais
    Trimestrais: ExpectativasMercadoTrimestrais, ExpectativaMercadoTop5Trimestral
    Selic:      ExpectativasMercadoSelic, ExpectativasMercadoTop5Selic
    Inflação:   ExpectativasMercadoInflacao12Meses, ExpectativasMercadoInflacao24Meses,
                ExpectativasMercadoTop5Inflacao12Meses, ExpectativasMercadoTop5Inflacao24Meses
    Utility:    DatasReferencia

Nota: Top5Selic usa colunas em camelCase minúsculo (diferente dos demais PascalCase).
A normalização trata ambos os casos.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd

from carteira_auto.config.constants import constants
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
)

logger = get_logger(__name__)


class BCBFocusMixin:
    """Métodos Focus para expectativas de mercado via BCB OData.

    Cobre todos os 13 endpoints do serviço Expectativas.
    Métodos *_all() usam ThreadPoolExecutor para paralelismo.
    """

    # =========================================================================
    # SEÇÃO A: ANUAIS (ExpectativasMercadoAnuais)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_selic(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para Selic — projeções anuais.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'indicador_detalhe',
            'ano_alvo', 'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_anuais("Selic", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_ipca(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para IPCA — projeções anuais."""
        return self._fetch_focus_anuais("IPCA", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_pib(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para PIB Total — projeções anuais."""
        return self._fetch_focus_anuais("PIB Total", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_cambio(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para Câmbio (USD/BRL) — projeções anuais."""
        return self._fetch_focus_anuais("Câmbio", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_igpm(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para IGP-M — projeções anuais."""
        return self._fetch_focus_anuais("IGP-M", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_all(self, period_months: int = 24) -> dict[str, pd.DataFrame]:
        """Busca expectativas Focus anuais para todos os indicadores em paralelo.

        Returns:
            Dict {indicador: DataFrame}. Falhas individuais retornam DataFrame vazio.
        """
        return self._fetch_focus_batch(
            constants.BCB_FOCUS_INDICATORS_ANUAIS,
            self._fetch_focus_anuais,
            period_months,
        )

    # =========================================================================
    # SEÇÃO B: TOP5 ANUAIS (ExpectativasMercadoTop5Anuais)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_top5(self, indicator: str, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus Top5 — projeções anuais dos 5 analistas mais precisos.

        Args:
            indicator: Nome do indicador (ex: 'Selic', 'IPCA', 'PIB Total').
            period_months: Meses de histórico (default: 24).

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'ano_alvo', 'tipo_calculo',
            'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo']
        """
        return self._fetch_focus_top5_anuais(indicator, period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_top5_all(self, period_months: int = 24) -> dict[str, pd.DataFrame]:
        """Top5 anuais para todos os indicadores em paralelo."""
        return self._fetch_focus_batch(
            constants.BCB_FOCUS_INDICATORS_TOP5_ANUAIS,
            self._fetch_focus_top5_anuais,
            period_months,
        )

    # =========================================================================
    # SEÇÃO C: MENSAIS (ExpectativaMercadoMensais)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_monthly(
        self, indicator: str, period_months: int = 24
    ) -> pd.DataFrame:
        """Expectativas Focus mensais — projeções por mês-alvo.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'mes_alvo',
            'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_mensais(indicator, period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_monthly_all(self, period_months: int = 24) -> dict[str, pd.DataFrame]:
        """Focus mensais para todos os indicadores em paralelo."""
        return self._fetch_focus_batch(
            constants.BCB_FOCUS_INDICATORS_MENSAIS,
            self._fetch_focus_mensais,
            period_months,
        )

    # =========================================================================
    # SEÇÃO D: TOP5 MENSAIS (ExpectativasMercadoTop5Mensais)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_top5_monthly(
        self, indicator: str, period_months: int = 24
    ) -> pd.DataFrame:
        """Top5 mensais — projeções dos 5 mais precisos por mês-alvo.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'mes_alvo', 'tipo_calculo',
            'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo']
        """
        return self._fetch_focus_generic_top5(
            "ExpectativasMercadoTop5Mensais",
            indicator,
            period_months,
            ref_col="DataReferencia",
            ref_alias="mes_alvo",
        )

    # =========================================================================
    # SEÇÃO E: TRIMESTRAIS (ExpectativasMercadoTrimestrais)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_quarterly(
        self, indicator: str, period_months: int = 24
    ) -> pd.DataFrame:
        """Expectativas Focus trimestrais — projeções por trimestre-alvo.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'trimestre_alvo',
            'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_trimestrais(indicator, period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_quarterly_all(
        self, period_months: int = 24
    ) -> dict[str, pd.DataFrame]:
        """Focus trimestrais para todos os indicadores em paralelo."""
        return self._fetch_focus_batch(
            constants.BCB_FOCUS_INDICATORS_TRIMESTRAIS,
            self._fetch_focus_trimestrais,
            period_months,
        )

    # =========================================================================
    # SEÇÃO F: TOP5 TRIMESTRAIS (ExpectativaMercadoTop5Trimestral)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_top5_quarterly(
        self, indicator: str, period_months: int = 24
    ) -> pd.DataFrame:
        """Top5 trimestrais — projeções dos 5 mais precisos por trimestre.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'trimestre_alvo',
            'tipo_calculo', 'mediana', 'media', 'desvio_padrao', 'minimo',
            'maximo', 'respondentes']
        """
        return self._fetch_focus_generic_top5(
            "ExpectativaMercadoTop5Trimestral",
            indicator,
            period_months,
            ref_col="DataReferencia",
            ref_alias="trimestre_alvo",
            has_respondentes=True,
        )

    # =========================================================================
    # SEÇÃO G: SELIC COPOM (ExpectativasMercadoSelic)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_selic_copom(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para Selic por reunião COPOM.

        Inclui campo 'Reuniao' que identifica a reunião do COPOM alvo
        da expectativa (ex: 'R2/2026', 'R8/2025').

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'reuniao',
            'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_selic_copom(period_months)

    # =========================================================================
    # SEÇÃO H: TOP5 SELIC (ExpectativasMercadoTop5Selic)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_top5_selic(self, period_months: int = 24) -> pd.DataFrame:
        """Top5 Selic — 5 analistas mais precisos por reunião COPOM.

        ATENÇÃO: este endpoint usa colunas em camelCase minúsculo
        (diferente de todos os demais que usam PascalCase).

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'reuniao',
            'tipo_calculo', 'mediana', 'media', 'desvio_padrao',
            'coeficiente_variacao', 'minimo', 'maximo']
        """
        return self._fetch_focus_top5_selic(period_months)

    # =========================================================================
    # SEÇÃO I: INFLAÇÃO 12M (ExpectativasMercadoInflacao12Meses)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_ipca12m(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para IPCA 12 meses à frente (horizonte móvel).

        Inclui versão suavizada e não-suavizada.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'suavizada',
            'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_inflacao(
            "ExpectativasMercadoInflacao12Meses", "IPCA", period_months
        )

    # =========================================================================
    # SEÇÃO J: INFLAÇÃO 24M (ExpectativasMercadoInflacao24Meses)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_ipca24m(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para IPCA 24 meses à frente (horizonte longo).

        Avalia ancoragem de expectativas de inflação de médio prazo.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'suavizada',
            'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_inflacao(
            "ExpectativasMercadoInflacao24Meses", "IPCA", period_months
        )

    # =========================================================================
    # SEÇÃO K: TOP5 INFLAÇÃO 12M/24M
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_top5_ipca12m(self, period_months: int = 24) -> pd.DataFrame:
        """Top5 IPCA 12 meses — 5 analistas mais precisos, horizonte 12m.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'suavizada',
            'tipo_calculo', 'mediana', 'media', 'desvio_padrao',
            'minimo', 'maximo', 'respondentes']
        """
        return self._fetch_focus_top5_inflacao(
            "ExpectativasMercadoTop5Inflacao12Meses", "IPCA", period_months
        )

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_top5_ipca24m(self, period_months: int = 24) -> pd.DataFrame:
        """Top5 IPCA 24 meses — 5 analistas mais precisos, horizonte 24m.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'suavizada',
            'tipo_calculo', 'mediana', 'media', 'desvio_padrao',
            'minimo', 'maximo', 'respondentes']
        """
        return self._fetch_focus_top5_inflacao(
            "ExpectativasMercadoTop5Inflacao24Meses", "IPCA", period_months
        )

    # =========================================================================
    # SEÇÃO L: DATAS DE REFERÊNCIA (DatasReferencia)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_focus_reference_dates(self) -> pd.DataFrame:
        """Datas de referência disponíveis para consulta Focus.

        Returns:
            DataFrame com colunas: ['indicador', 'periodo',
            'data_referencia_1', 'data_referencia_2']
        """
        return self._fetch_focus_reference_dates()

    # =========================================================================
    # INTERNOS — Motores por tipo de endpoint
    # =========================================================================

    def _fetch_focus_anuais(self, indicator: str, period_months: int) -> pd.DataFrame:
        """Motor para ExpectativasMercadoAnuais."""
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoAnuais")
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == indicator)
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.IndicadorDetalhe,
                ep.Data,
                ep.DataReferencia,
                ep.Mediana,
                ep.Media,
                ep.DesvioPadrao,
                ep.Minimo,
                ep.Maximo,
                ep.numeroRespondentes,
                ep.baseCalculo,
            )
            .collect()
        )

        if df is None or df.empty:
            logger.warning(f"Focus {indicator}: sem dados")
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "IndicadorDetalhe": "indicador_detalhe",
                "Data": "data",
                "DataReferencia": "ano_alvo",
                "Mediana": "mediana",
                "Media": "media",
                "DesvioPadrao": "desvio_padrao",
                "Minimo": "minimo",
                "Maximo": "maximo",
                "numeroRespondentes": "respondentes",
                "baseCalculo": "base_calculo",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus {indicator}: {len(df)} projeções")
        return df

    def _fetch_focus_top5_anuais(
        self, indicator: str, period_months: int
    ) -> pd.DataFrame:
        """Motor para ExpectativasMercadoTop5Anuais."""
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoTop5Anuais")
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == indicator)
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.Data,
                ep.DataReferencia,
                ep.tipoCalculo,
                ep.Media,
                ep.Mediana,
                ep.DesvioPadrao,
                ep.Minimo,
                ep.Maximo,
            )
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "Data": "data",
                "DataReferencia": "ano_alvo",
                "tipoCalculo": "tipo_calculo",
                "Media": "media",
                "Mediana": "mediana",
                "DesvioPadrao": "desvio_padrao",
                "Minimo": "minimo",
                "Maximo": "maximo",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus Top5 {indicator}: {len(df)} projeções")
        return df

    def _fetch_focus_mensais(self, indicator: str, period_months: int) -> pd.DataFrame:
        """Motor para ExpectativaMercadoMensais."""
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("ExpectativaMercadoMensais")
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == indicator)
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.Data,
                ep.DataReferencia,
                ep.Media,
                ep.Mediana,
                ep.DesvioPadrao,
                ep.Minimo,
                ep.Maximo,
                ep.numeroRespondentes,
                ep.baseCalculo,
            )
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "Data": "data",
                "DataReferencia": "mes_alvo",
                "Media": "media",
                "Mediana": "mediana",
                "DesvioPadrao": "desvio_padrao",
                "Minimo": "minimo",
                "Maximo": "maximo",
                "numeroRespondentes": "respondentes",
                "baseCalculo": "base_calculo",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus Mensal {indicator}: {len(df)} projeções")
        return df

    def _fetch_focus_trimestrais(
        self, indicator: str, period_months: int
    ) -> pd.DataFrame:
        """Motor para ExpectativasMercadoTrimestrais."""
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoTrimestrais")
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == indicator)
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.Data,
                ep.DataReferencia,
                ep.Media,
                ep.Mediana,
                ep.DesvioPadrao,
                ep.Minimo,
                ep.Maximo,
                ep.numeroRespondentes,
                ep.baseCalculo,
            )
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "Data": "data",
                "DataReferencia": "trimestre_alvo",
                "Media": "media",
                "Mediana": "mediana",
                "DesvioPadrao": "desvio_padrao",
                "Minimo": "minimo",
                "Maximo": "maximo",
                "numeroRespondentes": "respondentes",
                "baseCalculo": "base_calculo",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus Trimestral {indicator}: {len(df)} projeções")
        return df

    def _fetch_focus_selic_copom(self, period_months: int) -> pd.DataFrame:
        """Motor para ExpectativasMercadoSelic (por reunião COPOM)."""
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoSelic")
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == "Selic")
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.Data,
                ep.Reuniao,
                ep.Media,
                ep.Mediana,
                ep.DesvioPadrao,
                ep.Minimo,
                ep.Maximo,
                ep.numeroRespondentes,
                ep.baseCalculo,
            )
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "Data": "data",
                "Reuniao": "reuniao",
                "Media": "media",
                "Mediana": "mediana",
                "DesvioPadrao": "desvio_padrao",
                "Minimo": "minimo",
                "Maximo": "maximo",
                "numeroRespondentes": "respondentes",
                "baseCalculo": "base_calculo",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus Selic COPOM: {len(df)} projeções")
        return df

    def _fetch_focus_top5_selic(self, period_months: int) -> pd.DataFrame:
        """Motor para ExpectativasMercadoTop5Selic.

        ATENÇÃO: colunas retornadas em camelCase minúsculo (diferente dos demais).
        Colunas: indicador, Data, reuniao, tipoCalculo, media, mediana,
                 desvioPadrao, coeficienteVariacao, minimo, maximo
        """
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoTop5Selic")
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.indicador,
                ep.Data,
                ep.reuniao,
                ep.tipoCalculo,
                ep.media,
                ep.mediana,
                ep.desvioPadrao,
                ep.coeficienteVariacao,
                ep.minimo,
                ep.maximo,
            )
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        # Normalização especial: colunas minúsculas + PascalCase misto
        df = df.rename(
            columns={
                "indicador": "indicador",
                "Data": "data",
                "reuniao": "reuniao",
                "tipoCalculo": "tipo_calculo",
                "media": "media",
                "mediana": "mediana",
                "desvioPadrao": "desvio_padrao",
                "coeficienteVariacao": "coeficiente_variacao",
                "minimo": "minimo",
                "maximo": "maximo",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus Top5 Selic: {len(df)} projeções")
        return df

    def _fetch_focus_inflacao(
        self, endpoint_name: str, indicator: str, period_months: int
    ) -> pd.DataFrame:
        """Motor genérico para endpoints de inflação (12m e 24m).

        Colunas: Indicador, Data, Suavizada, Media, Mediana, DesvioPadrao,
                 Minimo, Maximo, numeroRespondentes, baseCalculo
        """
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint(endpoint_name)
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == indicator)
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.Data,
                ep.Suavizada,
                ep.Media,
                ep.Mediana,
                ep.DesvioPadrao,
                ep.Minimo,
                ep.Maximo,
                ep.numeroRespondentes,
                ep.baseCalculo,
            )
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "Data": "data",
                "Suavizada": "suavizada",
                "Media": "media",
                "Mediana": "mediana",
                "DesvioPadrao": "desvio_padrao",
                "Minimo": "minimo",
                "Maximo": "maximo",
                "numeroRespondentes": "respondentes",
                "baseCalculo": "base_calculo",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus {endpoint_name} {indicator}: {len(df)} registros")
        return df

    def _fetch_focus_top5_inflacao(
        self, endpoint_name: str, indicator: str, period_months: int
    ) -> pd.DataFrame:
        """Motor genérico para Top5 inflação (12m e 24m).

        Colunas: Indicador, Data, Suavizada, Media, Mediana, DesvioPadrao,
                 Minimo, Maximo, numeroRespondentes, tipoCalculo
        """
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint(endpoint_name)
        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == indicator)
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.Data,
                ep.Suavizada,
                ep.tipoCalculo,
                ep.Media,
                ep.Mediana,
                ep.DesvioPadrao,
                ep.Minimo,
                ep.Maximo,
                ep.numeroRespondentes,
            )
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "Data": "data",
                "Suavizada": "suavizada",
                "tipoCalculo": "tipo_calculo",
                "Media": "media",
                "Mediana": "mediana",
                "DesvioPadrao": "desvio_padrao",
                "Minimo": "minimo",
                "Maximo": "maximo",
                "numeroRespondentes": "respondentes",
            }
        )
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus {endpoint_name} {indicator}: {len(df)} registros")
        return df

    def _fetch_focus_generic_top5(
        self,
        endpoint_name: str,
        indicator: str,
        period_months: int,
        ref_col: str = "DataReferencia",
        ref_alias: str = "referencia",
        has_respondentes: bool = False,
    ) -> pd.DataFrame:
        """Motor genérico para Top5 com DataReferencia (mensais e trimestrais).

        Colunas comuns: Indicador, Data, DataReferencia, tipoCalculo,
                       Media, Mediana, DesvioPadrao, Minimo, Maximo
        """
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint(endpoint_name)
        start_date = date.today() - timedelta(days=period_months * 30)

        select_cols = [
            ep.Indicador,
            ep.Data,
            getattr(ep, ref_col),
            ep.tipoCalculo,
            ep.Media,
            ep.Mediana,
            ep.DesvioPadrao,
            ep.Minimo,
            ep.Maximo,
        ]
        if has_respondentes:
            select_cols.append(ep.numeroRespondentes)

        df = (
            ep.query()
            .filter(ep.Indicador == indicator)
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(*select_cols)
            .collect()
        )

        if df is None or df.empty:
            return pd.DataFrame()

        rename_map = {
            "Indicador": "indicador",
            "Data": "data",
            ref_col: ref_alias,
            "tipoCalculo": "tipo_calculo",
            "Media": "media",
            "Mediana": "mediana",
            "DesvioPadrao": "desvio_padrao",
            "Minimo": "minimo",
            "Maximo": "maximo",
        }
        if has_respondentes:
            rename_map["numeroRespondentes"] = "respondentes"

        df = df.rename(columns=rename_map)
        df["data"] = pd.to_datetime(df["data"])
        logger.debug(f"Focus {endpoint_name} {indicator}: {len(df)} projeções")
        return df

    def _fetch_focus_reference_dates(self) -> pd.DataFrame:
        """Motor para DatasReferencia."""
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("DatasReferencia")
        df = ep.query().collect()

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "periodo": "periodo",
                "DataReferencia1": "data_referencia_1",
                "DataReferencia2": "data_referencia_2",
            }
        )
        logger.debug(f"Focus DatasReferencia: {len(df)} registros")
        return df

    # =========================================================================
    # HELPER — Batch paralelo
    # =========================================================================

    @staticmethod
    def _fetch_focus_batch(
        indicators: list[str],
        fetch_fn: callable,
        period_months: int,
    ) -> dict[str, pd.DataFrame]:
        """Executa fetch_fn para cada indicador em paralelo.

        Falhas individuais retornam DataFrame vazio sem interromper os demais.
        """
        results: dict[str, pd.DataFrame] = {}

        def _fetch_one(indicator: str) -> tuple[str, pd.DataFrame]:
            try:
                df = fetch_fn(indicator, period_months)
                logger.debug(f"Focus batch {indicator}: {len(df)} registros")
                return indicator, df
            except Exception as e:
                logger.warning(f"Focus batch {indicator}: falha — {e}")
                return indicator, pd.DataFrame()

        with ThreadPoolExecutor(max_workers=min(len(indicators), 5)) as executor:
            futures = {executor.submit(_fetch_one, ind): ind for ind in indicators}
            for future in as_completed(futures):
                indicator, df = future.result()
                results[indicator] = df

        return results
