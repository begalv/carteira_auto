"""Fetcher do Banco Central do Brasil (BCB).

Pacote modular com cobertura máxima das APIs do BCB:
    - SGS: 60 séries temporais (bcb.sgs → HTTP fallback)
    - Focus: 13 endpoints de expectativas de mercado (bcb.Expectativas OData)
    - PTAX: 3 endpoints de câmbio oficial (bcb.PTAX OData)
    - TaxaJuros: 5 endpoints de taxas de crédito (bcb.TaxaJuros OData)
    - OData extras: IFDATA, MercadoImobiliário, SPI, DinheiroCirculação

Arquitetura: BCBFetcher compõe submódulos via herança múltipla.
Cada submódulo é um arquivo com métodos agrupados por fonte OData.

Uso:
    from carteira_auto.data.fetchers.bcb import BCBFetcher

    fetcher = BCBFetcher()
    df_selic = fetcher.get_selic()
    df_focus = fetcher.get_focus_ipca()
    df_ptax = fetcher.get_ptax_currency('USD')
"""

from carteira_auto.data.fetchers.bcb._base import BCBBaseMixin
from carteira_auto.data.fetchers.bcb._focus import BCBFocusMixin
from carteira_auto.data.fetchers.bcb._ptax import BCBPTAXMixin
from carteira_auto.data.fetchers.bcb._sgs import BCBSGSMixin
from carteira_auto.data.fetchers.bcb._taxajuros import BCBTaxaJurosMixin


class BCBFetcher(
    BCBBaseMixin, BCBSGSMixin, BCBFocusMixin, BCBPTAXMixin, BCBTaxaJurosMixin
):
    """Fetcher para dados do Banco Central do Brasil.

    Composição modular via herança múltipla:
        - BCBBaseMixin: config, logger, motor SGS dual (bcb.sgs → HTTP)
        - BCBSGSMixin: 57 séries SGS (seções 1-11)
        - BCBFocusMixin: 13 endpoints Focus (expectativas de mercado)
        - BCBPTAXMixin: PTAX câmbio oficial (3 endpoints OData)
        - BCBTaxaJurosMixin: taxas de crédito bancário (5 endpoints OData)

    Módulos pendentes:
        - BCBODataExtrasMixin: IFDATA, MercadoImobiliário, SPI, DinheiroCirculação
    """

    def __init__(self) -> None:
        super().__init__()


__all__ = ["BCBFetcher"]
