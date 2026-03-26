"""Modelos de dados da carteira de investimentos."""


from pydantic import BaseModel, field_validator


def _validate_non_negative(v: float | None, field_name: str) -> float | None:
    """Valida que valor numérico é >= 0 quando presente."""
    if v is not None and v < 0:
        raise ValueError(f"{field_name} não pode ser negativo: {v}")
    return v


class Asset(BaseModel):
    """Ativo na carteira — mapeia uma linha da aba 'Carteira'.

    Campos obrigatórios: ticker e nome.
    Campos numéricos de preço, posição e cotas devem ser >= 0.
    """

    ticker: str
    nome: str
    classe: str | None = None
    setor: str | None = None
    subsetor: str | None = None
    segmento: str | None = None
    pct_meta: float | None = None
    valor_meta: float | None = None
    pct_atual: float | None = None
    pct_inicial: float | None = None
    posicao_atual: float | None = None
    preco_posicao: float | None = None
    valorizacao: float | None = None
    valorizacao_pct: float | None = None
    proventos_recebidos: float | None = None
    diferenca: float | None = None
    rentabilidade: float | None = None
    rentabilidade_proporcional: float | None = None
    preco_atual: float | None = None
    preco_medio: float | None = None
    n_cotas_atual: float | None = None

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
