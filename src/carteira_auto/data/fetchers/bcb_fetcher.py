"""Fetcher do Banco Central do Brasil (BCB).

Motor interno: bcb (python-bcb, primário) → HTTP SGS (fallback automático).

Módulos bcb utilizados:
    - bcb.sgs: Séries temporais SGS (Sistema Gerenciador de Séries Temporais)
    - bcb.Expectativas: Relatório Focus — projeções de mercado via OData API
    - bcb.PTAX: Cotações PTAX de câmbio — todas as moedas via OData API
    - bcb.TaxaJuros: Taxas de juros do crédito bancário via OData API

API SGS (fallback HTTP):
    https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json
    Sem autenticação. Rate limit: usar 30 req/min por segurança.

Endpoints OData disponíveis:
    Expectativas: ExpectativasMercadoAnuais, ExpectativasMercadoInflacao12Meses,
                  ExpectativasMercadoSelic, ExpectativaMercadoMensais, ...
    PTAX: CotacaoMoedaPeriodo (MM-DD-YYYY), CotacaoMoedaDia, Moedas
    TaxaJuros: TaxasJurosMensalPorMes, ParametrosConsulta, ConsultaUnificada
"""

from datetime import date, timedelta

import pandas as pd
import requests

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

# Re-exportados para compatibilidade com código que importe diretamente deste módulo.
# Fonte canônica: constants.BCB_FOCUS_INDICATORS_ANUAIS / BCB_PTAX_MAIN_CURRENCIES
FOCUS_INDICATORS_ANUAIS: list[str] = constants.BCB_FOCUS_INDICATORS_ANUAIS
PTAX_MAIN_CURRENCIES: list[str] = constants.BCB_PTAX_MAIN_CURRENCIES


class BCBFetcher:
    """Fetcher para dados do Banco Central do Brasil.

    Motor SGS: bcb.sgs (primário) → HTTP SGS raw (fallback automático).

    Módulos adicionais via bcb (todos via OData API):
        - Focus (Expectativas): projeções de mercado com todas as estatísticas
        - PTAX: cotações oficiais para todas as moedas disponíveis
        - TaxaJuros: taxas de crédito mensais por modalidade e instituição
    """

    def __init__(self) -> None:
        self._base_url = settings.bcb.BASE_URL
        self._timeout = settings.bcb.TIMEOUT
        self._series = constants.BCB_SERIES_CODES

    # =========================================================================
    # SEÇÃO 1: TAXAS DE JUROS E RENDIMENTO (SGS)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_selic(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa Selic meta — % a.a. | Reuniões COPOM (~8×/ano) | SGS 432.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.a.
        """
        return self._fetch_sgs_series("selic", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_cdi(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """CDI diário — % a.d. | Divulgação diária (dias úteis) | SGS 12.

        Args:
            period_days: Número de dias retroativos (default: 5 anos = 1825 dias).

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.d.
            Para % a.a.: ((1 + valor/100) ** 252 - 1) * 100
        """
        return self._fetch_sgs_series("cdi", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_cdi_annual(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """CDI anualizado — % a.a. | SGS 4389.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.a.
        """
        return self._fetch_sgs_series("cdi_anualizado", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_tr(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa Referencial (TR) — % a.m. | Divulgação mensal | SGS 226.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.m.
        """
        return self._fetch_sgs_series("tr", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_poupanca(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Rendimento da poupança — % a.m. | Divulgação mensal | SGS 25.

        Desde maio/2012: TR + 0,5% a.m. quando Selic <= 8,5% a.a.;
        ou 70% Selic/252 + TR quando Selic > 8,5% a.a.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.m.
            Para % a.a.: ((1 + valor/100) ** 12 - 1) * 100
        """
        return self._fetch_sgs_series("poupanca", period_days)

    # =========================================================================
    # SEÇÃO 2: INFLAÇÃO (SGS)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ipca(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IPCA — variação mensal (%) | Divulgação ~9 dias após fim do mês | SGS 433.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
            Para acumulado 12m: ((1 + v/100).prod() - 1) * 100
        """
        return self._fetch_sgs_series("ipca", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_igpm(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IGP-M — variação mensal (%) | Divulgação ~último dia útil do mês | SGS 189.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_sgs_series("igpm", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_inpc(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """INPC — variação mensal (%) | Divulgação ~9 dias após fim do mês | SGS 188.

        Mede inflação para famílias com renda de 1 a 5 salários mínimos.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_sgs_series("inpc", period_days)

    # =========================================================================
    # SEÇÃO 3: CÂMBIO — SGS
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax(self, period_days: int = 30) -> pd.DataFrame:
        """Dólar PTAX compra — R$/USD | Dias úteis | SGS 10813.

        Mantido para backward compatibility. Para todas as moedas via OData,
        use get_ptax_currency() ou get_ptax_all_currencies().

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$/USD.
        """
        return self._fetch_sgs_series("ptax_compra", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax_venda(self, period_days: int = 30) -> pd.DataFrame:
        """Dólar PTAX venda — R$/USD | Dias úteis | SGS 1.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$/USD.
        """
        return self._fetch_sgs_series("ptax_venda", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_real_effective_exchange(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa de câmbio real efetiva deflacionada por IPCA — índice | SGS 11752.

        Mede a competitividade da taxa de câmbio em termos reais frente a uma
        cesta ponderada das moedas dos principais parceiros comerciais do Brasil.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é índice (base 100).
        """
        return self._fetch_sgs_series("taxa_cambio_real", period_days)

    # =========================================================================
    # SEÇÃO 4: FISCAL (SGS)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_gross_debt_gdp(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Dívida Bruta do Governo Geral / PIB — % | SGS 13762.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % do PIB.
        """
        return self._fetch_sgs_series("divida_bruta_pib", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_net_debt_gdp(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Dívida Líquida do Setor Público / PIB — % | SGS 4503.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % do PIB.
        """
        return self._fetch_sgs_series("divida_liquida_pib", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_primary_result_gdp(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Resultado Primário acumulado 12 meses / PIB — % | SGS 5793.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % do PIB.
        """
        return self._fetch_sgs_series("resultado_primario_pib", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_nominal_result(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Resultado Nominal acumulado 12 meses — R$ milhões | SGS 4649.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("resultado_nominal", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_nominal_interest_gdp(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Juros Nominais acumulados 12 meses / PIB — % | SGS 5727.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % do PIB.
        """
        return self._fetch_sgs_series("juros_nominais_pib", period_days)

    # =========================================================================
    # SEÇÃO 5: ATIVIDADE ECONÔMICA E MERCADO (SGS)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ibcbr(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IBC-Br — Índice de Atividade Econômica do BCB (proxy mensal do PIB) | SGS 24364.

        Proxy mensal do PIB com dessazonalização. Divulgado com defasagem de ~2 meses.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é índice dessazonalizado.
        """
        return self._fetch_sgs_series("ibc_br", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_business_confidence(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Índice de Confiança Empresarial — índice | SGS 7344.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é índice.
        """
        return self._fetch_sgs_series("confianca_empresario", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_embi(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """EMBI+ Brasil — risco-país em pontos base | SGS 40940.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é pontos base.
        """
        return self._fetch_sgs_series("embi_brasil", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ibovespa_bcb(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Índice Bovespa (fechamento) via BCB — pontos | SGS 7.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é pontos do IBOV.
        """
        return self._fetch_sgs_series("ibovespa_bcb", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ouro_bmf(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Cotação do ouro BM&F — R$/grama | SGS 4.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$/g.
        """
        return self._fetch_sgs_series("ouro_bmf", period_days)

    # =========================================================================
    # SEÇÃO 6: CRÉDITO E AGREGADOS MONETÁRIOS (SGS)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_credit_gdp(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Crédito total ao setor privado / PIB — % | SGS 20539.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % do PIB.
        """
        return self._fetch_sgs_series("credito_pib", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_default_rate(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Inadimplência de Pessoa Física — % da carteira de crédito | SGS 21085.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % da carteira.
        """
        return self._fetch_sgs_series("inadimplencia_pf", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_m1(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Agregado monetário M1 (papel-moeda + depósitos à vista) — R$ milhões | SGS 27789.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("m1", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_m2(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Agregado monetário M2 (M1 + depósitos especiais + poupança) — R$ milhões | SGS 27810.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("m2", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_m4(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Agregado monetário M4 (inclui títulos públicos) — R$ milhões | SGS 27815.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("m4", period_days)

    # =========================================================================
    # SEÇÃO 7: SETOR EXTERNO (SGS)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_trade_balance(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Saldo da balança comercial mensal — US$ milhões | SGS 22707.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é US$ milhões.
        """
        return self._fetch_sgs_series("balanca_comercial", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_international_reserves(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Reservas internacionais (conceito de liquidez) — US$ milhões | SGS 3546.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é US$ milhões.
        """
        return self._fetch_sgs_series("reservas_internacionais", period_days)

    # =========================================================================
    # SEÇÃO 8: FOCUS — EXPECTATIVAS DE MERCADO (via bcb.Expectativas OData)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_selic(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para Selic — projeções anuais com todas as estatísticas.

        Inclui: Mediana, Média, Mínimo, Máximo, Desvio Padrão e n respondentes,
        segmentado por ano-alvo de projeção.

        Args:
            period_months: Meses de histórico de projeções (default: 24 meses).

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'indicador_detalhe',
            'ano_alvo', 'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_anuais("Selic", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_ipca(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para IPCA — projeções anuais com todas as estatísticas.

        Args:
            period_months: Meses de histórico de projeções (default: 24 meses).

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'indicador_detalhe',
            'ano_alvo', 'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_anuais("IPCA", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_pib(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para PIB Total — projeções anuais com todas as estatísticas.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'indicador_detalhe',
            'ano_alvo', 'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_anuais("PIB Total", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_cambio(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para Câmbio (USD/BRL) — projeções anuais.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'indicador_detalhe',
            'ano_alvo', 'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_anuais("Câmbio", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_igpm(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para IGP-M — projeções anuais.

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'indicador_detalhe',
            'ano_alvo', 'mediana', 'media', 'desvio_padrao', 'minimo', 'maximo',
            'respondentes', 'base_calculo']
        """
        return self._fetch_focus_anuais("IGP-M", period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_ipca12m(self, period_months: int = 24) -> pd.DataFrame:
        """Expectativas Focus para IPCA acumulado nos próximos 12 meses (horizonte móvel).

        Diferente das projeções anuais: reflete expectativa de inflação para os
        próximos 12 meses a partir da data de referência (horizonte deslizante).
        Inclui versão suavizada e não-suavizada da expectativa.

        Args:
            period_months: Meses de histórico de projeções (default: 24 meses).

        Returns:
            DataFrame com colunas: ['data', 'indicador', 'suavizada', 'mediana',
            'media', 'desvio_padrao', 'minimo', 'maximo', 'respondentes', 'base_calculo']
        """
        return self._fetch_focus_ipca12m(period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_focus_all(self, period_months: int = 24) -> dict[str, pd.DataFrame]:
        """Busca expectativas Focus para todos os principais indicadores anuais.

        Coleta em série para evitar rate limiting. Falhas individuais retornam
        DataFrame vazio sem interromper os demais.

        Args:
            period_months: Meses de histórico de projeções (default: 24 meses).

        Returns:
            Dict {indicador: DataFrame} com todas as estatísticas disponíveis.
        """
        results: dict[str, pd.DataFrame] = {}
        for indicator in FOCUS_INDICATORS_ANUAIS:
            try:
                df = self._fetch_focus_anuais(indicator, period_months)
                results[indicator] = df
                logger.debug(f"Focus {indicator}: {len(df)} registros")
            except Exception as e:
                logger.warning(f"Focus {indicator}: falha — {e}")
                results[indicator] = pd.DataFrame()
        return results

    # =========================================================================
    # SEÇÃO 9: PTAX — CÂMBIO OFICIAL (via bcb.PTAX OData)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax_currency(
        self,
        currency_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period_days: int = 30,
    ) -> pd.DataFrame:
        """PTAX de fechamento para qualquer moeda com cotação no BCB.

        Suporta todas as moedas disponíveis: USD, EUR, GBP, CHF, JPY, AUD, CAD,
        CNY, ARS, MXN, DKK, NOK, SEK e outras. Ver get_available_currencies().

        Args:
            currency_code: Código ISO 4217 da moeda (ex: 'USD', 'EUR', 'CNY').
                           Case-insensitive — convertido para maiúsculas.
            start_date: Data inicial. Se None, usa period_days atrás.
            end_date: Data final. Se None, usa hoje.
            period_days: Usado apenas se start_date não for informado (default: 30).

        Returns:
            DataFrame com colunas: ['data', 'compra', 'venda', 'moeda'].
            'data' é datetime normalizado (sem hora), 'compra'/'venda' são float em R$.
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=period_days)
        return self._fetch_ptax_currency(currency_code.upper(), start_date, end_date)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax_all_currencies(
        self, reference_date: date | None = None
    ) -> pd.DataFrame:
        """PTAX de fechamento para todas as moedas disponíveis em uma data.

        Faz uma requisição por moeda. Para datas sem pregão (fins de semana
        e feriados), pode retornar DataFrame vazio ou com cotações do dia útil anterior.

        Args:
            reference_date: Data da cotação (default: hoje).

        Returns:
            DataFrame com colunas: ['simbolo', 'nome', 'compra', 'venda', 'data'].
        """
        if reference_date is None:
            reference_date = date.today()
        return self._fetch_ptax_all_currencies(reference_date)

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_available_currencies(self) -> pd.DataFrame:
        """Lista todas as moedas com cotação PTAX disponíveis no BCB.

        Returns:
            DataFrame com colunas: ['simbolo', 'nome', 'tipo_moeda'].
            tipo_moeda: 'A' = cotação direta, 'B' = cotação indireta.
        """
        return self._fetch_available_currencies()

    # =========================================================================
    # SEÇÃO 10: TAXAS DE CRÉDITO (via bcb.TaxaJuros OData)
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
            modality: Nome exato da modalidade (ex: 'Crédito pessoal não consignado',
                      'Cheque especial', 'Financiamento imobiliário PF').
                      Se None, retorna todas as modalidades disponíveis.
            period_months: Meses de histórico (default: 12 meses).

        Returns:
            DataFrame com colunas: ['mes', 'modalidade', 'posicao', 'instituicao',
            'taxa_mes', 'taxa_ano', 'cnpj8', 'ano_mes'].
            'taxa_mes' e 'taxa_ano' são % (ex: 2.5 = 2,5% a.m.).
        """
        return self._fetch_lending_rates(modality, period_months)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_all_lending_rates(self, period_months: int = 12) -> dict[str, pd.DataFrame]:
        """Taxas de juros para todas as modalidades, agrupadas por modalidade.

        Otimizado: faz uma única requisição à API e agrupa por modalidade,
        evitando múltiplas chamadas.

        Args:
            period_months: Meses de histórico (default: 12 meses).

        Returns:
            Dict {nome_modalidade: DataFrame} com dados por modalidade.
            Cada DataFrame tem colunas: ['mes', 'posicao', 'instituicao',
            'taxa_mes', 'taxa_ano', 'cnpj8', 'ano_mes'].
        """
        return self._fetch_all_lending_rates(period_months)

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_lending_rate_modalities(self) -> pd.DataFrame:
        """Lista todas as modalidades de crédito disponíveis no BCB.

        Útil para descobrir os nomes exatos das modalidades para uso
        em get_lending_rates(modality=...).

        Returns:
            DataFrame com colunas: ['codigo_modalidade', 'modalidade',
            'codigo_segmento', 'segmento', 'tipo_modalidade'].
        """
        return self._fetch_lending_rate_modalities()

    # =========================================================================
    # SEÇÃO 11: GENÉRICOS (SGS)
    # =========================================================================

    @log_execution
    def get_indicator(
        self,
        series_code: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Busca qualquer série do SGS por código numérico.

        Use este método para séries não cobertas pelos métodos específicos,
        ou para consultas com janelas de datas precisas.

        Args:
            series_code: Código da série no SGS (ex: 432 = Selic).
            start_date: Data inicial (default: 5 anos atrás).
            end_date: Data final (default: hoje).

        Returns:
            DataFrame com colunas ['data', 'valor'].
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=5 * 365)
        return self._fetch_sgs_raw(series_code, start_date, end_date)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_all_indicators(self) -> dict[str, pd.DataFrame]:
        """Busca todos os indicadores configurados em constants.BCB_SERIES_CODES.

        Returns:
            Dict {nome_indicador: DataFrame}. DataFrame vazio em caso de falha.
        """
        results: dict[str, pd.DataFrame] = {}
        for name, code in self._series.items():
            try:
                df = self._fetch_sgs_series(name)
                results[name] = df
                logger.debug(f"BCB {name}: {len(df)} registros")
            except Exception as e:
                logger.warning(f"Falha ao buscar BCB {name} (código {code}): {e}")
                results[name] = pd.DataFrame(columns=["data", "valor"])
        return results

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_latest_values(self) -> dict[str, float | None]:
        """Retorna o valor mais recente de cada indicador SGS configurado.

        Returns:
            Dict {nome_indicador: valor_float | None}.
        """
        results: dict[str, float | None] = {}
        for name in self._series:
            try:
                df = self._fetch_sgs_series(name, period_days=30)
                results[name] = float(df["valor"].iloc[-1]) if not df.empty else None
            except Exception as e:
                logger.warning(f"Falha ao buscar último valor BCB {name}: {e}")
                results[name] = None
        return results

    # =========================================================================
    # INTERNOS — SGS (bcb.sgs primário → HTTP fallback)
    # =========================================================================

    def _fetch_sgs_series(self, name: str, period_days: int = 5 * 365) -> pd.DataFrame:
        """Busca série SGS por nome configurado. Motor: bcb.sgs → HTTP fallback."""
        code = self._series.get(name)
        if code is None:
            raise ValueError(
                f"Série '{name}' não configurada. "
                f"Disponíveis: {list(self._series.keys())}"
            )
        end_dt = date.today()
        start_dt = end_dt - timedelta(days=period_days)
        return self._fetch_sgs_raw(code, start_dt, end_dt)

    def _fetch_sgs_raw(
        self, series_code: int, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca série SGS por código. Tenta bcb.sgs; fallback para HTTP."""
        try:
            return self._fetch_via_bcb_sgs(series_code, start_date, end_date)
        except Exception as e:
            logger.warning(
                f"bcb.sgs falhou para série {series_code}: {e}. "
                "Usando fallback HTTP SGS."
            )
            return self._fetch_raw(series_code, start_date, end_date)

    def _fetch_via_bcb_sgs(
        self, series_code: int, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca série via bcb.sgs (motor primário).

        O formato do dict {name: code} determina o nome da coluna retornada.
        bcb.sgs retorna DataFrame com DatetimeIndex nomeado 'Date'.
        """
        from bcb import sgs

        df = sgs.get(
            {"valor": series_code},
            start=start_date,
            end=end_date,
        )

        if df is None or df.empty:
            return pd.DataFrame(columns=["data", "valor"])

        # Normaliza: bcb.sgs → DatetimeIndex 'Date', col 'valor' → ['data', 'valor']
        df = df.reset_index()
        df.columns = ["data", "valor"]
        df["data"] = pd.to_datetime(df["data"])
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"])

        logger.debug(f"bcb.sgs série {series_code}: {len(df)} registros")
        return df

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_raw(
        self, series_code: int, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca série via HTTP SGS (fallback).

        API: GET /dados/serie/bcdata.sgs.{code}/dados?formato=json
             &dataInicial=DD/MM/YYYY&dataFinal=DD/MM/YYYY
        """
        url = self._base_url.format(code=series_code)
        params = {
            "formato": "json",
            "dataInicial": start_date.strftime("%d/%m/%Y"),
            "dataFinal": end_date.strftime("%d/%m/%Y"),
        }

        logger.debug(f"BCB HTTP SGS: série {series_code} de {start_date} a {end_date}")
        response = requests.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()

        data = response.json()
        if not data:
            logger.warning(f"Série {series_code}: sem dados no período")
            return pd.DataFrame(columns=["data", "valor"])

        df = pd.DataFrame(data)
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"])

        logger.debug(f"HTTP SGS {series_code}: {len(df)} registros")
        return df

    # =========================================================================
    # INTERNOS — FOCUS (bcb.Expectativas OData)
    # =========================================================================

    def _fetch_focus_anuais(self, indicator: str, period_months: int) -> pd.DataFrame:
        """Busca projeções anuais do Focus com todas as estatísticas disponíveis.

        Endpoint: ExpectativasMercadoAnuais
        Colunas disponíveis: Indicador, IndicadorDetalhe, Data, DataReferencia,
            Media, Mediana, DesvioPadrao, Minimo, Maximo, numeroRespondentes, baseCalculo
        """
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
            logger.warning(f"Focus {indicator}: sem dados para o período")
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

    def _fetch_focus_ipca12m(self, period_months: int) -> pd.DataFrame:
        """Busca expectativa IPCA 12 meses à frente (horizonte móvel).

        Endpoint: ExpectativasMercadoInflacao12Meses
        Colunas: Indicador, Data, Suavizada, Media, Mediana, DesvioPadrao,
                 Minimo, Maximo, numeroRespondentes, baseCalculo
        Nota: sem 'DataReferencia' (ano-alvo) — horizonte é sempre 12m à frente.
        """
        from bcb import Expectativas

        em = Expectativas()
        ep = em.get_endpoint("ExpectativasMercadoInflacao12Meses")

        start_date = date.today() - timedelta(days=period_months * 30)

        df = (
            ep.query()
            .filter(ep.Indicador == "IPCA")
            .filter(ep.Data >= start_date.strftime("%Y-%m-%d"))
            .select(
                ep.Indicador,
                ep.Data,
                ep.Suavizada,
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
            return pd.DataFrame()

        df = df.rename(
            columns={
                "Indicador": "indicador",
                "Data": "data",
                "Suavizada": "suavizada",
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

        logger.debug(f"Focus IPCA 12m: {len(df)} registros")
        return df

    # =========================================================================
    # INTERNOS — PTAX (bcb.PTAX OData)
    # =========================================================================

    def _fetch_ptax_currency(
        self, currency_code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca cotação PTAX de fechamento para uma moeda específica via BCB.

        Fonte única: BCB PTAX OData (CotacaoMoedaPeriodo).
        Moedas suportadas: AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, SEK, USD.

        Para moedas não suportadas (CNY, ARS, MXN, etc.), retorna DataFrame vazio.
        O fallback para outras fontes (ex: Yahoo Finance) é responsabilidade
        dos IngestNodes via fetch_with_fallback() — conforme arquitetura do projeto.

        Retorna DataFrame com colunas ['data', 'compra', 'venda', 'moeda', 'fonte'].
        """
        empty = pd.DataFrame(columns=["data", "compra", "venda", "moeda", "fonte"])
        bcb_supported = constants.BCB_PTAX_SUPPORTED_CURRENCIES

        if currency_code not in bcb_supported:
            logger.info(
                f"PTAX {currency_code}: moeda não suportada pelo BCB PTAX "
                f"(suportadas: {', '.join(sorted(bcb_supported))}). "
                "Fallback deve ser orquestrado pelo IngestNode."
            )
            return empty

        try:
            from bcb import PTAX

            ptax = PTAX()
            ep = ptax.get_endpoint("CotacaoMoedaPeriodo")
            raw = (
                ep.query()
                .parameters(
                    moeda=currency_code,
                    dataInicial=start_date.strftime("%m-%d-%Y"),
                    dataFinalCotacao=end_date.strftime("%m-%d-%Y"),
                )
                .filter(ep.tipoBoletim == "Fechamento")
                .select(ep.cotacaoCompra, ep.cotacaoVenda, ep.dataHoraCotacao)
                .collect()
            )

            if raw is None or raw.empty:
                logger.warning(f"PTAX {currency_code}: BCB retornou vazio")
                return empty

            raw = raw.rename(
                columns={
                    "cotacaoCompra": "compra",
                    "cotacaoVenda": "venda",
                    "dataHoraCotacao": "data",
                }
            )
            raw["data"] = pd.to_datetime(raw["data"]).dt.normalize()
            raw["moeda"] = currency_code
            raw["fonte"] = "bcb_ptax"
            df = raw[["data", "compra", "venda", "moeda", "fonte"]].reset_index(
                drop=True
            )
            logger.debug(f"PTAX {currency_code}: {len(df)} cotações via BCB PTAX")
            return df

        except Exception as exc:
            logger.warning(f"PTAX {currency_code}: falha no BCB PTAX ({exc})")
            return empty

    def _fetch_ptax_all_currencies(self, reference_date: date) -> pd.DataFrame:
        """Busca PTAX de fechamento para todas as moedas disponíveis em uma data.

        Estratégia: lista moedas via endpoint Moedas, depois busca cada uma
        individualmente via CotacaoMoedaDia. Falhas individuais são ignoradas.
        """
        from bcb import PTAX

        ptax = PTAX()

        # Lista de moedas disponíveis
        ep_moedas = ptax.get_endpoint("Moedas")
        df_moedas = ep_moedas.query().collect()

        if df_moedas is None or df_moedas.empty:
            logger.warning("PTAX Moedas: lista indisponível")
            return pd.DataFrame(columns=["simbolo", "nome", "compra", "venda", "data"])

        ep_dia = ptax.get_endpoint("CotacaoMoedaDia")
        date_str = reference_date.strftime("%m-%d-%Y")

        results = []
        for _, row in df_moedas.iterrows():
            simbolo = row["simbolo"]
            try:
                df_cot = (
                    ep_dia.query()
                    .parameters(moeda=simbolo, dataCotacao=date_str)
                    .filter(ep_dia.tipoBoletim == "Fechamento")
                    .select(ep_dia.cotacaoCompra, ep_dia.cotacaoVenda)
                    .collect()
                )
                if df_cot is not None and not df_cot.empty:
                    results.append(
                        {
                            "simbolo": simbolo,
                            "nome": row.get("nomeFormatado", ""),
                            "compra": df_cot["cotacaoCompra"].iloc[-1],
                            "venda": df_cot["cotacaoVenda"].iloc[-1],
                            "data": pd.Timestamp(reference_date),
                        }
                    )
            except Exception as e:
                logger.debug(f"PTAX {simbolo} em {reference_date}: sem cotação — {e}")

        if not results:
            return pd.DataFrame(columns=["simbolo", "nome", "compra", "venda", "data"])

        df_result = pd.DataFrame(results)
        logger.debug(
            f"PTAX all currencies em {reference_date}: {len(df_result)} moedas"
        )
        return df_result

    def _fetch_available_currencies(self) -> pd.DataFrame:
        """Lista todas as moedas com cotação PTAX disponíveis no BCB.

        Endpoint: Moedas (EntitySet)
        Colunas: simbolo, nomeFormatado, tipoMoeda
        """
        from bcb import PTAX

        ptax = PTAX()
        ep = ptax.get_endpoint("Moedas")
        df = ep.query().collect()

        if df is None or df.empty:
            logger.warning("PTAX Moedas: indisponível, retornando lista padrão")
            n = len(PTAX_MAIN_CURRENCIES)
            return pd.DataFrame(
                {
                    "simbolo": PTAX_MAIN_CURRENCIES,
                    "nome": [""] * n,
                    "tipo_moeda": [""] * n,
                }
            )

        df = df.rename(
            columns={
                "nomeFormatado": "nome",
                "tipoMoeda": "tipo_moeda",
            }
        )

        logger.debug(f"PTAX Moedas: {len(df)} moedas disponíveis")
        return df[["simbolo", "nome", "tipo_moeda"]].reset_index(drop=True)

    # =========================================================================
    # INTERNOS — TAXAJUROS (bcb.TaxaJuros OData)
    # =========================================================================

    def _fetch_lending_rates(
        self, modality: str | None, period_months: int
    ) -> pd.DataFrame:
        """Busca taxas de crédito mensais, opcionalmente filtradas por modalidade.

        Endpoint: TaxasJurosMensalPorMes (EntitySet)
        Colunas: Mes, Modalidade, Posicao, InstituicaoFinanceira,
                 TaxaJurosAoMes, TaxaJurosAoAno, cnpj8, anoMes
        """
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

        df = self._normalize_lending_rates(df)
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

        df_all = self._normalize_lending_rates(df_all)

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

    @staticmethod
    def _normalize_lending_rates(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza DataFrame de taxas de crédito para colunas snake_case."""
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
