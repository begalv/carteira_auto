"""BCBFetcher — TaxaJuros (Taxas de Crédito via bcb.TaxaJuros OData).

Endpoints utilizados (5/5):
    - TaxasJurosMensalPorMes: taxas mensais por modalidade e instituição
    - ParametrosConsulta: lista de modalidades disponíveis
    - TaxasJurosDiariaPorInicioPeriodo: taxas diárias (média 5 dias)
    - ConsultaUnificada: consulta integrada (mesmas colunas do diário)
    - ConsultaDatas: datas disponíveis para consulta
"""

from datetime import date, timedelta

import pandas as pd

from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
)

logger = get_logger(__name__)


class BCBTaxaJurosMixin:
    """Métodos para taxas de crédito bancário via BCB OData.

    Cobre todas as modalidades de crédito PF e PJ, com dados por instituição.
    """

    # =========================================================================
    # MÉTODOS PÚBLICOS
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_lending_rates(
        self,
        modality: str | None = None,
        period_months: int = 12,
    ) -> pd.DataFrame:
        """Taxas de juros mensais do crédito bancário por modalidade e instituição.

        Args:
            modality: Nome exato da modalidade (ex: 'Crédito pessoal não consignado').
                      Se None, retorna todas as modalidades disponíveis.
            period_months: Meses de histórico (default: 12 meses).

        Returns:
            DataFrame com colunas: ['mes', 'modalidade', 'posicao', 'instituicao',
            'taxa_mes', 'taxa_ano', 'cnpj8', 'ano_mes'].
        """
        return self._fetch_lending_rates(modality, period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_all_lending_rates(self, period_months: int = 12) -> dict[str, pd.DataFrame]:
        """Taxas de juros para todas as modalidades, agrupadas por modalidade.

        Args:
            period_months: Meses de histórico (default: 12 meses).

        Returns:
            Dict {nome_modalidade: DataFrame} com dados por modalidade.
        """
        return self._fetch_all_lending_rates(period_months)

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_lending_rate_modalities(self) -> pd.DataFrame:
        """Lista todas as modalidades de crédito disponíveis no BCB.

        Returns:
            DataFrame com colunas: ['codigo_modalidade', 'modalidade',
            'codigo_segmento', 'segmento', 'tipo_modalidade'].
        """
        return self._fetch_lending_rate_modalities()

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_lending_rates_daily(
        self,
        modality: str | None = None,
        segment: str | None = None,
        period_months: int = 3,
    ) -> pd.DataFrame:
        """Taxas de juros diárias (média 5 dias) por modalidade e instituição.

        Endpoint: TaxasJurosDiariaPorInicioPeriodo. Granularidade mais fina
        que get_lending_rates() (mensal).

        Args:
            modality: Nome da modalidade. Se None, retorna todas.
            segment: Segmento ('PESSOA FÍSICA', 'PESSOA JURÍDICA'). Se None, todos.
            period_months: Meses de histórico (default: 3).

        Returns:
            DataFrame com colunas: ['inicio_periodo', 'fim_periodo', 'segmento',
            'modalidade', 'posicao', 'instituicao', 'taxa_mes', 'taxa_ano', 'cnpj8'].
        """
        return self._fetch_lending_rates_daily(modality, segment, period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_lending_rates_unified(
        self,
        modality: str | None = None,
        segment: str | None = None,
        period_months: int = 3,
    ) -> pd.DataFrame:
        """Consulta unificada de taxas de crédito (mesma estrutura do diário).

        Endpoint: ConsultaUnificada. Alternativa ao TaxasJurosDiariaPorInicioPeriodo.

        Args:
            modality: Nome da modalidade. Se None, retorna todas.
            segment: Segmento. Se None, todos.
            period_months: Meses de histórico (default: 3).

        Returns:
            DataFrame com colunas: ['inicio_periodo', 'fim_periodo', 'segmento',
            'modalidade', 'posicao', 'instituicao', 'taxa_mes', 'taxa_ano', 'cnpj8'].
        """
        return self._fetch_lending_rates_odata(
            "ConsultaUnificada", modality, segment, period_months
        )

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_lending_rate_dates(self) -> pd.DataFrame:
        """Datas disponíveis para consulta de taxas de crédito.

        Returns:
            DataFrame com colunas: ['inicio_periodo', 'fim_periodo', 'tipo_modalidade'].
        """
        return self._fetch_lending_rate_dates()

    # =========================================================================
    # INTERNOS — TaxaJuros (bcb.TaxaJuros OData)
    # =========================================================================

    def _fetch_lending_rates(
        self, modality: str | None, period_months: int
    ) -> pd.DataFrame:
        """Busca taxas de crédito mensais via TaxasJurosMensalPorMes."""
        from bcb import TaxaJuros

        tj = TaxaJuros()
        ep = tj.get_endpoint("TaxasJurosMensalPorMes")

        start_date = date.today() - timedelta(days=period_months * 30)

        query = ep.query().filter(ep.Mes >= start_date.strftime("%Y-%m-%d"))
        if modality is not None:
            query = query.filter(ep.Modalidade == modality)

        df = query.collect()

        if df is None or df.empty:
            return pd.DataFrame()

        df = self._normalize_lending_rates_monthly(df)
        logger.debug(f"TaxaJuros ('{modality or 'todas'}'): {len(df)} registros")
        return df

    def _fetch_all_lending_rates(self, period_months: int) -> dict[str, pd.DataFrame]:
        """Busca todas as modalidades em uma requisição e agrupa por modalidade."""
        from bcb import TaxaJuros

        tj = TaxaJuros()
        ep = tj.get_endpoint("TaxasJurosMensalPorMes")

        start_date = date.today() - timedelta(days=period_months * 30)
        df_all = ep.query().filter(ep.Mes >= start_date.strftime("%Y-%m-%d")).collect()

        if df_all is None or df_all.empty:
            return {}

        df_all = self._normalize_lending_rates_monthly(df_all)

        results: dict[str, pd.DataFrame] = {}
        for modality, group in df_all.groupby("modalidade"):
            results[str(modality)] = group.drop(
                columns=["modalidade"], errors="ignore"
            ).reset_index(drop=True)

        logger.debug(f"TaxaJuros: {len(results)} modalidades encontradas")
        return results

    def _fetch_lending_rate_modalities(self) -> pd.DataFrame:
        """Lista modalidades disponíveis via ParametrosConsulta."""
        from bcb import TaxaJuros

        tj = TaxaJuros()
        ep = tj.get_endpoint("ParametrosConsulta")
        df = ep.query().collect()

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "codigoModalidade": "codigo_modalidade",
                "modalidade": "modalidade",
                "codigoSegmento": "codigo_segmento",
                "segmento": "segmento",
                "tipoModalidade": "tipo_modalidade",
            }
        )

        logger.debug(f"TaxaJuros modalidades: {len(df)} encontradas")
        return df

    def _fetch_lending_rates_daily(
        self,
        modality: str | None,
        segment: str | None,
        period_months: int,
    ) -> pd.DataFrame:
        """Busca taxas diárias via TaxasJurosDiariaPorInicioPeriodo."""
        return self._fetch_lending_rates_odata(
            "TaxasJurosDiariaPorInicioPeriodo", modality, segment, period_months
        )

    def _fetch_lending_rates_odata(
        self,
        endpoint_name: str,
        modality: str | None,
        segment: str | None,
        period_months: int,
    ) -> pd.DataFrame:
        """Motor genérico para endpoints TaxaJuros com colunas diárias.

        Usado por TaxasJurosDiariaPorInicioPeriodo e ConsultaUnificada.
        """
        from bcb import TaxaJuros

        tj = TaxaJuros()
        ep = tj.get_endpoint(endpoint_name)

        start_date = date.today() - timedelta(days=period_months * 30)

        query = ep.query().filter(ep.InicioPeriodo >= start_date.strftime("%Y-%m-%d"))
        if modality is not None:
            query = query.filter(ep.Modalidade == modality)
        if segment is not None:
            query = query.filter(ep.Segmento == segment)

        df = query.collect()

        if df is None or df.empty:
            return pd.DataFrame()

        df = self._normalize_lending_rates_daily(df)
        logger.debug(
            f"TaxaJuros {endpoint_name} "
            f"('{modality or 'todas'}', '{segment or 'todos'}'): {len(df)} registros"
        )
        return df

    def _fetch_lending_rate_dates(self) -> pd.DataFrame:
        """Busca datas disponíveis via ConsultaDatas."""
        from bcb import TaxaJuros

        tj = TaxaJuros()
        ep = tj.get_endpoint("ConsultaDatas")
        df = ep.query().collect()

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "inicioPeriodo": "inicio_periodo",
                "fimPeriodo": "fim_periodo",
                "tipoModalidade": "tipo_modalidade",
            }
        )

        logger.debug(f"TaxaJuros datas: {len(df)} períodos disponíveis")
        return df

    # =========================================================================
    # NORMALIZAÇÃO
    # =========================================================================

    @staticmethod
    def _normalize_lending_rates_monthly(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza DataFrame de taxas mensais para colunas snake_case."""
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Mes": "mes",
                "Modalidade": "modalidade",
                "Posicao": "posicao",
                "InstituicaoFinanceira": "instituicao",
                "TaxaJurosAoMes": "taxa_mes",
                "TaxaJurosAoAno": "taxa_ano",
                "cnpj8": "cnpj8",
                "anoMes": "ano_mes",
            }
        )

        for col in ("taxa_mes", "taxa_ano"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.reset_index(drop=True)

    @staticmethod
    def _normalize_lending_rates_daily(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza DataFrame de taxas diárias para colunas snake_case."""
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "InicioPeriodo": "inicio_periodo",
                "FimPeriodo": "fim_periodo",
                "codigoSegmento": "codigo_segmento",
                "Segmento": "segmento",
                "codigoModalidade": "codigo_modalidade",
                "Modalidade": "modalidade",
                "Posicao": "posicao",
                "InstituicaoFinanceira": "instituicao",
                "TaxaJurosAoMes": "taxa_mes",
                "TaxaJurosAoAno": "taxa_ano",
                "cnpj8": "cnpj8",
            }
        )

        for col in ("taxa_mes", "taxa_ano"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.reset_index(drop=True)
