"""BCBFetcher — Métodos SGS (Sistema Gerenciador de Séries Temporais).

60 séries organizadas em 12 seções temáticas:
    1. Taxas de juros e rendimento
    2. Inflação
    3. Câmbio (SGS)
    4. Fiscal
    5. Atividade econômica e mercado
    6. Crédito e agregados monetários
    7. Setor externo
    8. Trabalho e renda
    9. Expropriação financeira
    10. Preços relativos
    11. Concentração e dominância financeira
    12. Emprego e produtividade
"""

from datetime import date, timedelta

import pandas as pd

from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
)

logger = get_logger(__name__)


class BCBSGSMixin:
    """Métodos públicos para séries SGS do BCB.

    Cada método retorna DataFrame['data', 'valor'] com cache de 1h.
    Motor interno: bcb.sgs (primário) → HTTP SGS (fallback) via BCBBaseMixin.
    """

    # =========================================================================
    # SEÇÃO 1: TAXAS DE JUROS E RENDIMENTO
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_selic(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa Selic meta — % a.a. | Reuniões COPOM (~8×/ano) | SGS 432.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.a.
        """
        return self._fetch_sgs_series("selic", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_cdi(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """CDI diário — % a.d. | Divulgação diária (dias úteis) | SGS 12.

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

        Desde mai/2012: TR + 0,5% a.m. quando Selic <= 8,5% a.a.;
        ou 70% Selic/252 + TR quando Selic > 8,5% a.a.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.m.
        """
        return self._fetch_sgs_series("poupanca", period_days)

    # =========================================================================
    # SEÇÃO 2: INFLAÇÃO
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ipca(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IPCA — variação mensal (%) | ~9 dias após fim do mês | SGS 433.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_sgs_series("ipca", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_igpm(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IGP-M — variação mensal (%) | ~último dia útil do mês | SGS 189.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_sgs_series("igpm", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_inpc(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """INPC — variação mensal (%) | Famílias 1 a 5 SM | SGS 188.

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
        """Taxa de câmbio real efetiva (IPCA) — índice | SGS 11752.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é índice (base 100).
        """
        return self._fetch_sgs_series("taxa_cambio_real", period_days)

    # =========================================================================
    # SEÇÃO 4: FISCAL
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
    # SEÇÃO 5: ATIVIDADE ECONÔMICA E MERCADO
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ibcbr(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IBC-Br — proxy mensal do PIB (dessazonalizado) | SGS 24364.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é índice.
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
            DataFrame com colunas ['data', 'valor'] onde valor é pontos.
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

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_capacity_utilization(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Utilização da capacidade instalada — indústria (FGV/CNI) | SGS 24352.

        Proxy da contradição entre forças produtivas e relações de produção.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("utilizacao_capacidade", period_days)

    # =========================================================================
    # SEÇÃO 6: CRÉDITO E AGREGADOS MONETÁRIOS
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
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("inadimplencia_pf", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_default_rate_corporate(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Inadimplência de Pessoa Jurídica — % da carteira | SGS 21082.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("inadimplencia_pj", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_default_rate_total(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Inadimplência total (PF + PJ) — % da carteira | SGS 21084.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("inadimplencia_total", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_default_rate_pf_15_90(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Inadimplência PF atraso 15-90 dias — % da carteira | SGS 27663.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("inadimplencia_pf_atraso_15_90", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_default_rate_pf_90_plus(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Inadimplência PF atraso >90 dias — % da carteira | SGS 27664.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("inadimplencia_pf_atraso_acima_90", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_default_rate_credit_card(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Inadimplência cartão de crédito — R$ milhões | SGS 22036.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("inadimplencia_cartao", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_m1(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Agregado monetário M1 — R$ milhões | SGS 27789.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("m1", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_m2(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Agregado monetário M2 — R$ milhões | SGS 27810.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("m2", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_m4(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Agregado monetário M4 — R$ milhões | SGS 27815.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("m4", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_monetary_base(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Base monetária — saldo fim de período — R$ milhões | SGS 1788.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("base_monetaria", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_reserve_requirements(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Recolhimento compulsório total — R$ milhões | SGS 1849.

        Controle estatal sobre o multiplicador bancário.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("compulsorios", period_days)

    # =========================================================================
    # SEÇÃO 7: SETOR EXTERNO
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
        """Reservas internacionais (liquidez) — US$ milhões | SGS 3546.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é US$ milhões.
        """
        return self._fetch_sgs_series("reservas_internacionais", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_current_account(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Transações correntes — saldo mensal — US$ milhões | SGS 22701.

        Déficit crônico revela transferência estrutural de valor periferia→centro.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é US$ milhões.
        """
        return self._fetch_sgs_series("conta_corrente", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_fdi_net(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Investimento Direto no País — líquido — US$ milhões | SGS 22704.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é US$ milhões.
        """
        return self._fetch_sgs_series("ied_liquido", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_external_debt(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Dívida externa total registrada — US$ milhões | SGS 3547.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é US$ milhões.
        """
        return self._fetch_sgs_series("divida_externa_total", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_fx_flow(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Fluxo cambial total — mensal — US$ milhões | SGS 22706.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é US$ milhões.
        """
        return self._fetch_sgs_series("fluxo_cambial", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_terms_of_trade(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Índice de termos de troca — export/import — índice | SGS 27574.

        Deterioração secular dos termos de troca é o mecanismo prebischiano.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é índice.
        """
        return self._fetch_sgs_series("termos_troca", period_days)

    # =========================================================================
    # SEÇÃO 8: TRABALHO E RENDA (contradição capital-trabalho)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_real_wage_bill(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Massa salarial real — habitual — PNAD — R$ milhões | SGS 11777.

        Base material da capacidade de investimento da PF.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$ milhões.
        """
        return self._fetch_sgs_series("massa_salarial_real", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_real_average_income(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Rendimento médio real habitual — PNAD — R$ | SGS 24382.

        Proxy do valor da força de trabalho.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$.
        """
        return self._fetch_sgs_series("rendimento_medio_real", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_unemployment_rate(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa de desocupação — PNAD trimestral — % | SGS 24369.

        Exército industrial de reserva — pressiona salários.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("taxa_desocupacao", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_minimum_wage(self, period_days: int = 10 * 365) -> pd.DataFrame:
        """Salário mínimo vigente — R$ | SGS 1619.

        Piso legal da reprodução da força de trabalho.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é R$.
        """
        return self._fetch_sgs_series("salario_minimo", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_formal_employment_balance(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """CAGED — saldo de empregos formais — unidades | SGS 28763.

        Formalização vs. precarização do trabalho.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é unidades.
        """
        return self._fetch_sgs_series("caged_saldo", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_hours_worked(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Horas habitualmente trabalhadas — PNAD — horas/semana | SGS 28544.

        Intensidade da exploração do trabalho.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é horas/semana.
        """
        return self._fetch_sgs_series("horas_trabalhadas", period_days)

    # =========================================================================
    # SEÇÃO 9: EXPROPRIAÇÃO FINANCEIRA (contradição capital financeiro vs. PF)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_banking_spread_pf(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Spread bancário médio — PF — total — p.p. | SGS 20786.

        Diferença entre custo de captação e taxa cobrada da PF.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é pontos percentuais.
        """
        return self._fetch_sgs_series("spread_bancario_pf", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_credit_cost_pf(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Taxa média de juros — PF — total — % a.a. | SGS 20749.

        Custo real do endividamento para a PF.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.a.
        """
        return self._fetch_sgs_series("custo_credito_pf", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_household_debt_ratio(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Endividamento famílias com SFN / renda acum. 12m — % | SGS 29037.

        Grau de subordinação financeira das famílias ao capital bancário.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("endividamento_familias", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_household_debt_service(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Comprometimento de renda das famílias com SFN — % | SGS 29038.

        Proporção da renda apropriada pelo serviço da dívida.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é %.
        """
        return self._fetch_sgs_series("comprometimento_renda", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_consumer_confidence(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Índice de Confiança do Consumidor (Fecomércio) — índice | SGS 4393.

        Proxy da percepção econômica subjetiva da PF.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é índice.
        """
        return self._fetch_sgs_series("icc_fecomercio", period_days)

    # =========================================================================
    # SEÇÃO 10: PREÇOS RELATIVOS (contradição valor vs. preço)
    # =========================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ipca15(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IPCA-15 (prévia) — variação mensal (%) | SGS 7478.

        Early warning inflacionário antes do IPCA cheio.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_sgs_series("ipca15", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_igpdi(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """IGP-DI — variação mensal (%) | SGS 190.

        Capta inflação de atacado (IPA-DI peso 60%) que antecede varejo.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_sgs_series("igpdi", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_core_ipca_ex0(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Núcleo IPCA-EX0 — exclusão alimentação e energia — % | SGS 11427.

        Separa inflação estrutural (demanda/inércia) da inflação de choque.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é variação % mensal.
        """
        return self._fetch_sgs_series("nucleo_ipca_ex0", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ipca_expectation_12m(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Expectativa IPCA 12 meses (Focus mediana via SGS) — % | SGS 13522.

        Ancoragem de expectativas — sinal de confiança/desconfiança no Estado.

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % acumulado 12m.
        """
        return self._fetch_sgs_series("expectativa_ipca_12m", period_days)

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_real_interest_rate(self, period_days: int = 5 * 365) -> pd.DataFrame:
        """Selic real ex-ante (deflacionada pela expectativa IPCA) — % a.a. | SGS 4390.

        O preço que o Estado paga ao capital financeiro pela "confiança".

        Returns:
            DataFrame com colunas ['data', 'valor'] onde valor é % a.a. real.
        """
        return self._fetch_sgs_series("selic_real", period_days)

    # =========================================================================
    # SEÇÃO 11: GENÉRICOS
    # =========================================================================

    @log_execution
    def get_indicator(
        self,
        series_code: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Busca qualquer série do SGS por código numérico.

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

        Usa sgs.get(last=1) para eficiência — evita buscar períodos inteiros.

        Returns:
            Dict {nome_indicador: valor_float | None}.
        """
        results: dict[str, float | None] = {}
        for name, code in self._series.items():
            try:
                df = self._fetch_sgs_last(code, last_n=1)
                results[name] = float(df["valor"].iloc[-1]) if not df.empty else None
            except Exception as e:
                logger.warning(f"Falha ao buscar último valor BCB {name}: {e}")
                results[name] = None
        return results
