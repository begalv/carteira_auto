"""BCBFetcher — PTAX (Câmbio Oficial via bcb.PTAX OData).

Endpoints utilizados:
    - CotacaoMoedaPeriodo: cotações de fechamento para uma moeda em um período
    - CotacaoMoedaDia: cotação de fechamento para uma moeda em uma data
    - Moedas: lista de moedas disponíveis
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


class BCBPTAXMixin:
    """Métodos PTAX para cotações de câmbio oficiais do BCB.

    Suporta 10 moedas nativas (AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, SEK, USD).
    Para demais moedas, retorna DataFrame vazio — fallback via IngestNodes.
    """

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_ptax_currency(
        self,
        currency_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period_days: int = 30,
    ) -> pd.DataFrame:
        """PTAX de fechamento para moedas suportadas pelo BCB.

        Suporta as 10 moedas do BCB PTAX OData: AUD, CAD, CHF, DKK, EUR, GBP,
        JPY, NOK, SEK, USD. Para demais moedas (CNY, ARS, MXN, etc.), retorna
        DataFrame vazio — o fallback para outras fontes (Yahoo Finance, DDM)
        deve ser orquestrado pelo IngestNode via fetch_with_fallback().

        Args:
            currency_code: Código ISO 4217 da moeda (ex: 'USD', 'EUR').
            start_date: Data inicial. Se None, usa period_days atrás.
            end_date: Data final. Se None, usa hoje.
            period_days: Usado apenas se start_date não for informado (default: 30).

        Returns:
            DataFrame com colunas: ['data', 'compra', 'venda', 'moeda', 'fonte'].
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
        """
        return self._fetch_available_currencies()

    # =========================================================================
    # INTERNOS — PTAX (bcb.PTAX OData)
    # =========================================================================

    def _fetch_ptax_currency(
        self, currency_code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Busca cotação PTAX de fechamento para uma moeda via BCB OData.

        Fonte única: BCB PTAX OData (CotacaoMoedaPeriodo).
        Para moedas não suportadas, retorna DataFrame vazio.
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
        """Busca PTAX de fechamento para todas as moedas em uma data.

        Paralelismo: ThreadPoolExecutor com max 10 workers.
        Cada thread instancia seu próprio PTAX() para evitar race conditions.
        """
        from bcb import PTAX

        ptax = PTAX()

        ep_moedas = ptax.get_endpoint("Moedas")
        df_moedas = ep_moedas.query().collect()

        if df_moedas is None or df_moedas.empty:
            logger.warning("PTAX Moedas: lista indisponível")
            return pd.DataFrame(columns=["simbolo", "nome", "compra", "venda", "data"])

        date_str = reference_date.strftime("%m-%d-%Y")
        moedas_list = df_moedas.to_dict("records")

        def _fetch_one_currency(row: dict) -> dict | None:
            simbolo = row["simbolo"]
            try:
                ptax_t = PTAX()
                ep_dia = ptax_t.get_endpoint("CotacaoMoedaDia")
                df_cot = (
                    ep_dia.query()
                    .parameters(moeda=simbolo, dataCotacao=date_str)
                    .filter(ep_dia.tipoBoletim == "Fechamento")
                    .select(ep_dia.cotacaoCompra, ep_dia.cotacaoVenda)
                    .collect()
                )
                if df_cot is not None and not df_cot.empty:
                    return {
                        "simbolo": simbolo,
                        "nome": row.get("nomeFormatado", ""),
                        "compra": df_cot["cotacaoCompra"].iloc[-1],
                        "venda": df_cot["cotacaoVenda"].iloc[-1],
                        "data": pd.Timestamp(reference_date),
                    }
            except Exception as e:
                logger.debug(f"PTAX {simbolo} em {reference_date}: sem cotação — {e}")
            return None

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_fetch_one_currency, row) for row in moedas_list]
            for future in as_completed(futures):
                entry = future.result()
                if entry is not None:
                    results.append(entry)

        if not results:
            return pd.DataFrame(columns=["simbolo", "nome", "compra", "venda", "data"])

        df_result = pd.DataFrame(results)
        logger.debug(
            f"PTAX all currencies em {reference_date}: {len(df_result)} moedas"
        )
        return df_result

    def _fetch_available_currencies(self) -> pd.DataFrame:
        """Lista todas as moedas com cotação PTAX disponíveis no BCB."""
        from bcb import PTAX

        ptax = PTAX()
        ep = ptax.get_endpoint("Moedas")
        df = ep.query().collect()

        if df is None or df.empty:
            logger.warning("PTAX Moedas: indisponível, retornando lista padrão")
            fallback = constants.BCB_PTAX_MAIN_CURRENCIES
            n = len(fallback)
            return pd.DataFrame(
                {
                    "simbolo": fallback,
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
