"""BCBFetcher — Mercado Imobiliário (bcb.MercadoImobiliario OData).

Endpoint utilizado: mercadoimobiliario
    - Retorna 3 colunas: Data, Info (nome do indicador), Valor
    - ~2134 indicadores disponíveis — usamos 13 curados em Constants

Indicadores cobertos:
    - Índices: IVG (preços), MVG (garantias)
    - Crédito PF: estoque SFH, FGTS, Livre
    - Inadimplência PF: SFH, Livre
    - Taxas: crédito SFH, Livre
    - Contratações: fluxo SFH, Livre
    - Imóveis: apartamento, casa, valor médio
"""

from datetime import date, timedelta

import pandas as pd

from carteira_auto.config.constants import constants
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
    rate_limit,
    retry,
)

logger = get_logger(__name__)

# Mapa legível: chave interna → nome do indicador na coluna Info da API
_INDICATORS = constants.BCB_MERCADO_IMOBILIARIO_INDICATORS


class BCBMercadoImobiliarioMixin:
    """Métodos para indicadores do mercado imobiliário via BCB OData.

    Cobre índices de preço, crédito habitacional, inadimplência e contratações.
    Usa bcb.MercadoImobiliario como motor primário.
    """

    # =========================================================================
    # MÉTODOS PÚBLICOS — ÍNDICES
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ivg(self, period_months: int = 60) -> pd.DataFrame:
        """IVG — Índice de Valores de Garantia de Imóveis Residenciais.

        Proxy de preços de imóveis residenciais financiados no Brasil.

        Args:
            period_months: Meses de histórico (default: 60 = 5 anos).

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
        """
        return self._fetch_mercado_imobiliario("ivg", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_mvg(self, period_months: int = 60) -> pd.DataFrame:
        """MVG — Índice de Média dos Valores de Garantia.

        Valor médio dos imóveis dados como garantia em financiamentos.

        Args:
            period_months: Meses de histórico (default: 60 = 5 anos).

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
        """
        return self._fetch_mercado_imobiliario("mvg", period_months)

    # =========================================================================
    # MÉTODOS PÚBLICOS — CRÉDITO PF (ESTOQUE)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_credito_imobiliario_sfh(self, period_months: int = 60) -> pd.DataFrame:
        """Estoque de crédito imobiliário PF — SFH (Sistema Financeiro da Habitação).

        Saldo total de financiamentos habitacionais via SFH (recursos SBPE/poupança).

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = saldo em R$ (estoque).
        """
        return self._fetch_mercado_imobiliario("credito_pf_sfh_total", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_credito_imobiliario_fgts(self, period_months: int = 60) -> pd.DataFrame:
        """Estoque de crédito imobiliário PF — FGTS.

        Saldo total de financiamentos habitacionais via recursos do FGTS.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = saldo em R$ (estoque).
        """
        return self._fetch_mercado_imobiliario("credito_pf_fgts_total", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_credito_imobiliario_livre(self, period_months: int = 60) -> pd.DataFrame:
        """Estoque de crédito imobiliário PF — recursos livres.

        Saldo total de financiamentos com recursos livres (não direcionados).

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = saldo em R$ (estoque).
        """
        return self._fetch_mercado_imobiliario("credito_pf_livre_total", period_months)

    # =========================================================================
    # MÉTODOS PÚBLICOS — INADIMPLÊNCIA
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_inadimplencia_imobiliaria_sfh(
        self, period_months: int = 60
    ) -> pd.DataFrame:
        """Inadimplência do crédito imobiliário PF — SFH.

        Taxa de inadimplência dos financiamentos habitacionais via SFH.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = taxa de inadimplência (%).
        """
        return self._fetch_mercado_imobiliario(
            "inadimplencia_pf_sfh_total", period_months
        )

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_inadimplencia_imobiliaria_livre(
        self, period_months: int = 60
    ) -> pd.DataFrame:
        """Inadimplência do crédito imobiliário PF — recursos livres.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
        """
        return self._fetch_mercado_imobiliario(
            "inadimplencia_pf_livre_total", period_months
        )

    # =========================================================================
    # MÉTODOS PÚBLICOS — TAXAS DE CRÉDITO
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_taxa_credito_imobiliario_sfh(self, period_months: int = 60) -> pd.DataFrame:
        """Taxa média de crédito imobiliário PF — SFH.

        Taxa de juros média das novas contratações via SFH.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = taxa de juros média (% a.a.).
        """
        return self._fetch_mercado_imobiliario(
            "taxa_credito_pf_sfh_total", period_months
        )

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_taxa_credito_imobiliario_livre(
        self, period_months: int = 60
    ) -> pd.DataFrame:
        """Taxa média de crédito imobiliário PF — recursos livres.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = taxa de juros média (% a.a.).
        """
        return self._fetch_mercado_imobiliario(
            "taxa_credito_pf_livre_total", period_months
        )

    # =========================================================================
    # MÉTODOS PÚBLICOS — CONTRATAÇÕES (FLUXO)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_contratacao_imobiliaria_sfh(self, period_months: int = 60) -> pd.DataFrame:
        """Contratações de crédito imobiliário PF — SFH (fluxo mensal).

        Volume de novas contratações via SFH no período.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = valor contratado em R$.
        """
        return self._fetch_mercado_imobiliario(
            "contratacao_pf_sfh_total", period_months
        )

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_contratacao_imobiliaria_livre(
        self, period_months: int = 60
    ) -> pd.DataFrame:
        """Contratações de crédito imobiliário PF — recursos livres (fluxo mensal).

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = valor contratado em R$.
        """
        return self._fetch_mercado_imobiliario(
            "contratacao_pf_livre_total", period_months
        )

    # =========================================================================
    # MÉTODOS PÚBLICOS — IMÓVEIS
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_imoveis_apartamento(self, period_months: int = 60) -> pd.DataFrame:
        """Estoque de imóveis tipo apartamento em garantia.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
        """
        return self._fetch_mercado_imobiliario(
            "imoveis_tipo_apartamento_total", period_months
        )

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_imoveis_casa(self, period_months: int = 60) -> pd.DataFrame:
        """Estoque de imóveis tipo casa em garantia.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
        """
        return self._fetch_mercado_imobiliario("imoveis_tipo_casa_total", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_imoveis_valor_medio(self, period_months: int = 60) -> pd.DataFrame:
        """Valor médio dos imóveis em garantia.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
            valor = valor médio em R$.
        """
        return self._fetch_mercado_imobiliario(
            "imoveis_valor_medio_total", period_months
        )

    # =========================================================================
    # AGREGADOR
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_mercado_imobiliario_all(
        self, period_months: int = 60
    ) -> dict[str, pd.DataFrame]:
        """Todos os 13 indicadores imobiliários curados em um dict.

        Returns:
            Dict {nome_indicador: DataFrame} para cada indicador com dados.
            Indicadores com erro são omitidos com log de aviso.
        """
        result: dict[str, pd.DataFrame] = {}
        for indicator_key in _INDICATORS:
            try:
                df = self._fetch_mercado_imobiliario(indicator_key, period_months)
                if not df.empty:
                    result[indicator_key] = df
            except Exception as e:
                logger.warning(
                    f"MercadoImobiliário: erro ao buscar {indicator_key}: {e}"
                )
        logger.info(
            f"MercadoImobiliário: {len(result)}/{len(_INDICATORS)} indicadores obtidos"
        )
        return result

    # =========================================================================
    # INTERNOS
    # =========================================================================

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_mercado_imobiliario(
        self, indicator_key: str, period_months: int
    ) -> pd.DataFrame:
        """Busca indicador do mercado imobiliário via bcb.MercadoImobiliario OData.

        Args:
            indicator_key: Chave do indicador em BCB_MERCADO_IMOBILIARIO_INDICATORS
                (ex: 'ivg', 'credito_pf_sfh_total').
            period_months: Meses de histórico.

        Returns:
            DataFrame com colunas ['data', 'valor', 'indicador'].
        """
        indicator_info = _INDICATORS.get(indicator_key)
        if indicator_info is None:
            logger.error(
                f"MercadoImobiliário: indicador '{indicator_key}' não encontrado "
                f"em BCB_MERCADO_IMOBILIARIO_INDICATORS"
            )
            return pd.DataFrame(columns=["data", "valor", "indicador"])

        try:
            from bcb import MercadoImobiliario

            mi = MercadoImobiliario()
            ep = mi.get_endpoint("mercadoimobiliario")

            start_date = date.today() - timedelta(days=period_months * 30)

            df = (
                ep.query()
                .filter(ep.Info == indicator_info)
                .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
                .collect()
            )

            if df is None or df.empty:
                logger.debug(
                    f"MercadoImobiliário: '{indicator_key}' sem dados no período"
                )
                return pd.DataFrame(columns=["data", "valor", "indicador"])

            # Normaliza colunas para padrão do projeto
            result = pd.DataFrame(
                {
                    "data": pd.to_datetime(df["Data"]),
                    "valor": pd.to_numeric(df["Valor"], errors="coerce"),
                    "indicador": indicator_key,
                }
            )
            result = result.dropna(subset=["valor"]).sort_values("data")

            logger.debug(
                f"MercadoImobiliário '{indicator_key}': {len(result)} registros"
            )
            return result

        except ImportError:
            logger.warning(
                "python-bcb não instalado — MercadoImobiliário indisponível. "
                "Instale: pip install python-bcb>=0.6.0"
            )
            return pd.DataFrame(columns=["data", "valor", "indicador"])
        except Exception as e:
            logger.error(f"MercadoImobiliário '{indicator_key}': {e}")
            return pd.DataFrame(columns=["data", "valor", "indicador"])
