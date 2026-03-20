"""Modelos de dados da carteira de investimentos."""

from typing import Optional

from pydantic import BaseModel


class Asset(BaseModel):
    """Ativo na carteira — mapeia uma linha da aba 'Carteira'."""

    fator: str
    ticker: str
    nome: str
    classe: Optional[str] = None
    setor: Optional[str] = None
    subsetor: Optional[str] = None
    segmento: Optional[str] = None
    pct_meta: Optional[float] = None
    valor_meta: Optional[float] = None
    pct_atual: Optional[float] = None
    pct_inicial: Optional[float] = None
    posicao_atual: Optional[float] = None
    preco_posicao: Optional[float] = None
    valorizacao: Optional[float] = None
    valorizacao_pct: Optional[float] = None
    proventos_recebidos: Optional[float] = None
    diferenca: Optional[float] = None
    rentabilidade: Optional[float] = None
    rentabilidade_proporcional: Optional[float] = None
    preco_atual: Optional[float] = None
    preco_medio: Optional[str] = None
    n_cotas_atual: Optional[str] = None
    funcao_dialetica: Optional[str] = None


class SoldAsset(BaseModel):
    """Ativo vendido — mapeia uma linha da aba 'Vendas'."""

    categoria: str
    ticker: str
    nome: str
    classe: Optional[str] = None
    setor: Optional[str] = None
    valor_venda: Optional[float] = None
    preco_posicao: Optional[float] = None
    valorizacao: Optional[float] = None
    proventos_recebidos: Optional[float] = None
    diferenca: Optional[float] = None
    rentabilidade_individual: Optional[float] = None
    preco_na_venda: Optional[float] = None
    preco_medio_compra: Optional[float] = None
    n_cotas_vendidas: Optional[float] = None
    mes: Optional[str] = None


class Portfolio(BaseModel):
    """Estado completo da carteira num ponto no tempo."""

    assets: list[Asset]
    sold_assets: list[SoldAsset] = []
