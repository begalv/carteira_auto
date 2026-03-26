"""Modelos de dados da carteira de investimentos."""


from pydantic import BaseModel, field_validator


def _validate_non_negative(v: float | None, field_name: str) -> float | None:
    """Valida que valor numérico é >= 0 quando presente."""
    if v is not None and v < 0:
        raise ValueError(f"{field_name} não pode ser negativo: {v}")
    return v


class Asset(BaseModel):
    """Ativo na carteira — mapeia uma linha da aba 'Carteira' + dados fundamentalistas.

    Campos obrigatórios: ticker e nome.
    Campos numéricos de preço, posição e cotas devem ser >= 0.

    Estrutura de campos:
        - Identificação: ticker, nome, classe, setor, subsetor, segmento
        - Alocação: pct_meta, valor_meta, pct_atual, pct_inicial
        - Posição: posicao_atual, preco_posicao, preco_atual, preco_medio, n_cotas_atual
        - Performance: valorizacao, valorizacao_pct, proventos_recebidos,
                        diferenca, rentabilidade, rentabilidade_proporcional
        - Valuation: p_l, p_vp, ev_ebitda, dy_12m, market_cap
        - Qualidade: roe, roa, margem_liquida, margem_ebitda
        - Crescimento: receita_liquida, ebitda, cagr_receita_5a, lpa, vpa
        - Endividamento: divida_liquida_ebitda
        - Mercado: beta_5a, free_float, liquidez_media_diaria
    """

    # ---- Identificação ----
    ticker: str
    """Código do ativo (ex: PETR4, HGLG11, ^BVSP)."""

    nome: str
    """Nome completo do ativo ou fundo."""

    classe: str | None = None
    """Classe do ativo (ex: Ações, FII, Renda Fixa, Internacional)."""

    setor: str | None = None
    """Setor de atuação (ex: Petróleo & Gás, Shoppings)."""

    subsetor: str | None = None
    """Subsetor de atuação."""

    segmento: str | None = None
    """Segmento específico de atuação."""

    # ---- Alocação ----
    pct_meta: float | None = None
    """Percentual meta de alocação na carteira (%)."""

    valor_meta: float | None = None
    """Valor monetário meta de alocação (R$)."""

    pct_atual: float | None = None
    """Percentual atual de alocação na carteira (%)."""

    pct_inicial: float | None = None
    """Percentual de alocação no momento da compra (%)."""

    # ---- Posição ----
    posicao_atual: float | None = None
    """Valor financeiro atual da posição (R$)."""

    preco_posicao: float | None = None
    """Preço do ativo no momento do registro da posição (R$)."""

    preco_atual: float | None = None
    """Preço de mercado atual (R$)."""

    preco_medio: float | None = None
    """Preço médio de compra (R$)."""

    n_cotas_atual: float | None = None
    """Número de cotas/ações em carteira."""

    # ---- Performance ----
    valorizacao: float | None = None
    """Valorização absoluta da posição (R$)."""

    valorizacao_pct: float | None = None
    """Valorização percentual da posição (%)."""

    proventos_recebidos: float | None = None
    """Total de proventos/dividendos recebidos (R$)."""

    diferenca: float | None = None
    """Diferença entre posição atual e custo total (R$)."""

    rentabilidade: float | None = None
    """Rentabilidade total acumulada incluindo proventos (%)."""

    rentabilidade_proporcional: float | None = None
    """Rentabilidade proporcional ao peso na carteira (%)."""

    # ---- Valuation ----
    p_l: float | None = None
    """Preço/Lucro (P/E ratio) — vezes. Quanto o mercado paga por R$1 de lucro."""

    p_vp: float | None = None
    """Preço/Valor Patrimonial (P/BV) — vezes. Quanto o mercado paga por R$1 de patrimônio líquido."""

    ev_ebitda: float | None = None
    """EV/EBITDA — vezes. Valor da empresa em múltiplos do EBITDA."""

    dy_12m: float | None = None
    """Dividend Yield dos últimos 12 meses — % a.a. (dividendos / preço atual)."""

    market_cap: float | None = None
    """Capitalização de mercado (R$ MM)."""

    # ---- Qualidade ----
    roe: float | None = None
    """Return on Equity — % a.a. (lucro líquido / patrimônio líquido médio)."""

    roa: float | None = None
    """Return on Assets — % a.a. (lucro líquido / ativo total médio)."""

    margem_liquida: float | None = None
    """Margem Líquida — % (lucro líquido / receita líquida)."""

    margem_ebitda: float | None = None
    """Margem EBITDA — % (EBITDA / receita líquida)."""

    # ---- Crescimento ----
    receita_liquida: float | None = None
    """Receita Líquida — R$ MM (últimos 12 meses)."""

    ebitda: float | None = None
    """EBITDA — R$ MM (últimos 12 meses)."""

    lpa: float | None = None
    """Lucro por Ação — R$ (últimos 12 meses)."""

    vpa: float | None = None
    """Valor Patrimonial por Ação — R$ (último balanço)."""

    cagr_receita_5a: float | None = None
    """CAGR de Receita em 5 anos — % a.a. (taxa de crescimento composto anual)."""

    # ---- Endividamento ----
    divida_liquida_ebitda: float | None = None
    """Dívida Líquida / EBITDA — vezes. Alavancagem financeira."""

    # ---- Mercado ----
    beta_5a: float | None = None
    """Beta em 5 anos vs IBOV — adimensional. Sensibilidade ao mercado."""

    free_float: float | None = None
    """Free Float — % das ações em circulação no mercado."""

    liquidez_media_diaria: float | None = None
    """Liquidez Média Diária — R$ MM (volume médio negociado por dia)."""

    @field_validator("ticker")
    @classmethod
    def ticker_nao_vazio(cls, v: str) -> str:
        """Ticker deve ser uma string não vazia."""
        v = v.strip()
        if not v:
            raise ValueError("ticker não pode ser vazio")
        return v

    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        """Nome deve ser uma string não vazia."""
        v = v.strip()
        if not v:
            raise ValueError("nome não pode ser vazio")
        return v

    @field_validator("preco_atual", "preco_medio", "preco_posicao")
    @classmethod
    def precos_nao_negativos(cls, v: float | None, info) -> float | None:
        """Preços devem ser >= 0."""
        return _validate_non_negative(v, info.field_name)

    @field_validator("posicao_atual", "valor_meta")
    @classmethod
    def posicao_nao_negativa(cls, v: float | None, info) -> float | None:
        """Posição e valor meta devem ser >= 0."""
        return _validate_non_negative(v, info.field_name)

    @field_validator("n_cotas_atual")
    @classmethod
    def cotas_nao_negativas(cls, v: float | None, info) -> float | None:
        """Número de cotas deve ser >= 0."""
        return _validate_non_negative(v, info.field_name)

    @field_validator("pct_meta", "pct_atual", "pct_inicial")
    @classmethod
    def percentuais_nao_negativos(cls, v: float | None, info) -> float | None:
        """Percentuais de alocação devem ser >= 0."""
        return _validate_non_negative(v, info.field_name)


class SoldAsset(BaseModel):
    """Ativo vendido — mapeia uma linha da aba 'Vendas'.

    Campos obrigatórios: categoria, ticker e nome.
    Preços e cotas devem ser >= 0.
    """

    categoria: str
    ticker: str
    nome: str
    classe: str | None = None
    setor: str | None = None
    valor_venda: float | None = None
    preco_posicao: float | None = None
    valorizacao: float | None = None
    proventos_recebidos: float | None = None
    diferenca: float | None = None
    rentabilidade_individual: float | None = None
    preco_na_venda: float | None = None
    preco_medio_compra: float | None = None
    n_cotas_vendidas: float | None = None
    mes: str | None = None

    @field_validator("ticker")
    @classmethod
    def ticker_nao_vazio(cls, v: str) -> str:
        """Ticker deve ser uma string não vazia."""
        v = v.strip()
        if not v:
            raise ValueError("ticker não pode ser vazio")
        return v

    @field_validator("preco_na_venda", "preco_medio_compra", "preco_posicao")
    @classmethod
    def precos_nao_negativos(cls, v: float | None, info) -> float | None:
        """Preços devem ser >= 0."""
        return _validate_non_negative(v, info.field_name)

    @field_validator("n_cotas_vendidas")
    @classmethod
    def cotas_nao_negativas(cls, v: float | None, info) -> float | None:
        """Número de cotas deve ser >= 0."""
        return _validate_non_negative(v, info.field_name)


class Portfolio(BaseModel):
    """Estado completo da carteira num ponto no tempo.

    Deve conter ao menos um ativo.
    """

    assets: list[Asset]
    sold_assets: list[SoldAsset] = []

    @field_validator("assets")
    @classmethod
    def assets_nao_vazio(cls, v: list[Asset]) -> list[Asset]:
        """Portfolio deve ter ao menos um ativo."""
        if not v:
            raise ValueError("Portfolio deve conter ao menos um ativo")
        return v
