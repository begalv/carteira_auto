"""Fetcher do Tesouro Direto — Tesouro Transparente (dados abertos).

Portal: https://www.tesourotransparente.gov.br/ckan
API: Dados abertos via CSV/API CKAN (sem autenticação)
Docs: https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto

Fontes de dados:
    - Taxas de compra/venda e preços dos títulos ofertados (diário)
    - Fluxo de vendas por título e investidor
    - Estoque de LFT, NTN-B, LTN, NTN-F

Tipos de títulos suportados:
    - LFT: Tesouro Selic (pós-fixado)
    - NTN-B: Tesouro IPCA+ (com cupom)
    - NTN-B Principal: Tesouro IPCA+ (sem cupom)
    - LTN: Tesouro Prefixado (sem cupom)
    - NTN-F: Tesouro Prefixado (com cupom semestral)

Fluxo típico:
    fetcher = TesouroDiretoFetcher()

    # Taxas atuais disponíveis
    df_taxas = fetcher.get_current_rates()

    # Histórico de preços e taxas
    df_hist = fetcher.get_price_history()

    # Filtrado por tipo
    lft = fetcher.get_price_history_by_type("LFT")
    ntnb = fetcher.get_price_history_by_type("NTN-B")
"""

from __future__ import annotations

import io

import pandas as pd
import requests

from carteira_auto.config import settings
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
    rate_limit,
    retry,
)

logger = get_logger(__name__)

# URLs dos datasets no Tesouro Transparente (CKAN)
_BASE_URL = "https://www.tesourotransparente.gov.br/ckan/dataset"

# Taxas ofertadas no dia (preços de compra/venda atuais)
_URL_TAXAS_HOJE = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a53-8184-7ebd8700c6f4/resource/"
    "796d2059-14e9-44e3-80c9-ca2e93d4d793/download/PrecoTaxaTesouroDireto.csv"
)

# Histórico completo de preços e taxas (desde 2002)
_URL_HISTORICO = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a53-8184-7ebd8700c6f4/resource/"
    "796d2059-14e9-44e3-80c9-ca2e93d4d793/download/PrecoTaxaTesouroDireto.csv"
)

# Mapeamento: tipo normalizado → substring no campo "Tipo Titulo"
_TIPO_MAP = {
    "LFT": "LFT",  # Tesouro Selic
    "NTN-B": "NTN-B Principal",  # Tesouro IPCA+ sem cupom
    "NTN-B CUPOM": "NTN-B",  # Tesouro IPCA+ com cupom
    "LTN": "LTN",  # Tesouro Prefixado sem cupom
    "NTN-F": "NTN-F",  # Tesouro Prefixado com cupom
}

# Colunas do CSV do Tesouro (em português, com separador ";")
_COLUNAS_TESOURO = {
    "Tipo Titulo": "tipo",
    "Data Vencimento": "vencimento",
    "Data Base": "data",
    "Taxa Compra Manha": "taxa_compra",
    "Taxa Venda Manha": "taxa_venda",
    "PU Compra Manha": "pu_compra",
    "PU Venda Manha": "pu_venda",
    "PU Base Manha": "pu_base",
}


class TesouroDiretoFetcher:
    """Fetcher para dados históricos do Tesouro Direto.

    Sem autenticação — dados abertos do Tesouro Transparente.
    Fornece preços (PU) e taxas (% a.a.) de LFT, NTN-B, LTN e NTN-F.

    Uso:
        fetcher = TesouroDiretoFetcher()

        # Taxas e preços atuais
        df = fetcher.get_current_rates()

        # Histórico de LFT (Tesouro Selic)
        lft = fetcher.get_price_history_by_type("LFT")

        # Curva IPCA+ — spread histórico das NTN-B
        ntnb = fetcher.get_ntnb_curve()
    """

    def __init__(self) -> None:
        self._timeout = settings.tesouro.TIMEOUT
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "carteira_auto/1.0"})

    # ============================================================================
    # TAXAS ATUAIS
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_current_rates(self) -> pd.DataFrame:
        """Taxas e preços atuais dos títulos ofertados no Tesouro Direto.

        Retorna o último snapshot disponível com PU de compra/venda
        e taxas para todos os títulos em oferta.

        Returns:
            DataFrame com colunas: tipo, vencimento, data, taxa_compra,
            taxa_venda, pu_compra, pu_venda, pu_base.
        """
        logger.debug("TesouroDireto: buscando taxas atuais")
        df = self._fetch_csv(_URL_TAXAS_HOJE)

        # Filtra apenas a data mais recente
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
            ultima_data = df["data"].max()
            df = df[df["data"] == ultima_data].copy()
            logger.info(
                f"TesouroDireto: taxas de {ultima_data.date()}, {len(df)} títulos"
            )

        return df

    # ============================================================================
    # HISTÓRICO COMPLETO
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_price_history(self) -> pd.DataFrame:
        """Histórico completo de preços e taxas do Tesouro Direto (desde 2002).

        Arquivo grande (~10MB), cacheado por 24h. Contém todos os títulos
        disponíveis historicamente com PU e taxa para cada dia útil.

        Returns:
            DataFrame com colunas: tipo, vencimento, data, taxa_compra,
            taxa_venda, pu_compra, pu_venda, pu_base.
        """
        logger.debug("TesouroDireto: buscando histórico completo")
        df = self._fetch_csv(_URL_HISTORICO)

        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
        if "vencimento" in df.columns:
            df["vencimento"] = pd.to_datetime(
                df["vencimento"], dayfirst=True, errors="coerce"
            )

        # Converte taxas e PUs para numérico
        numeric_cols = ["taxa_compra", "taxa_venda", "pu_compra", "pu_venda", "pu_base"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", "."),
                    errors="coerce",
                )

        logger.info(f"TesouroDireto: histórico com {len(df)} observações")
        return df

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_price_history_by_type(self, tipo: str) -> pd.DataFrame:
        """Histórico filtrado por tipo de título.

        Args:
            tipo: Tipo do título. Opções: "LFT", "NTN-B", "NTN-B CUPOM",
                  "LTN", "NTN-F". Case-insensitive.

        Returns:
            DataFrame filtrado para o tipo especificado.

        Raises:
            ValueError: Tipo não reconhecido.
        """
        tipo_upper = tipo.upper()
        if tipo_upper not in _TIPO_MAP:
            raise ValueError(
                f"Tipo '{tipo}' não reconhecido. " f"Válidos: {list(_TIPO_MAP.keys())}"
            )

        df = self.get_price_history()
        if df.empty or "tipo" not in df.columns:
            return df

        subtipo = _TIPO_MAP[tipo_upper]

        if tipo_upper in ("NTN-B", "NTN-B CUPOM"):
            # Distingue NTN-B com e sem cupom
            if tipo_upper == "NTN-B":
                mask = df["tipo"].str.contains("NTN-B Principal", na=False)
            else:
                mask = df["tipo"].str.contains("NTN-B", na=False) & ~df[
                    "tipo"
                ].str.contains("Principal", na=False)
        else:
            mask = df["tipo"].str.contains(subtipo, na=False)

        filtered = df[mask].copy()
        logger.debug(f"TesouroDireto: {tipo} — {len(filtered)} observações")
        return filtered

    # ============================================================================
    # SÉRIES ESPECÍFICAS (CONVENIÊNCIA)
    # ============================================================================

    def get_lft_history(self) -> pd.DataFrame:
        """Histórico do LFT (Tesouro Selic) — pós-fixado referenciado à Selic."""
        return self.get_price_history_by_type("LFT")

    def get_ntnb_history(self, com_cupom: bool = False) -> pd.DataFrame:
        """Histórico das NTN-B (Tesouro IPCA+).

        Args:
            com_cupom: Se True, retorna NTN-B com cupom semestral;
                       se False, retorna NTN-B Principal (zero cupom).
        """
        tipo = "NTN-B CUPOM" if com_cupom else "NTN-B"
        return self.get_price_history_by_type(tipo)

    def get_ltn_history(self) -> pd.DataFrame:
        """Histórico do LTN (Tesouro Prefixado) — sem cupom."""
        return self.get_price_history_by_type("LTN")

    def get_ntnf_history(self) -> pd.DataFrame:
        """Histórico do NTN-F (Tesouro Prefixado com cupom semestral)."""
        return self.get_price_history_by_type("NTN-F")

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_ntnb_curve(self) -> pd.DataFrame:
        """Curva IPCA+ atual (NTN-B) — taxa por vencimento.

        Retorna snapshot do último dia disponível com taxa de cada
        NTN-B por vencimento. Útil para análise de spread e duration.

        Returns:
            DataFrame com vencimento, taxa_compra, taxa_venda,
            pu_compra, ordenado por vencimento crescente.
        """
        df_hist = self.get_ntnb_history(com_cupom=True)
        if df_hist.empty:
            df_hist = self.get_ntnb_history(com_cupom=False)

        if df_hist.empty or "data" not in df_hist.columns:
            return df_hist

        ultima_data = df_hist["data"].max()
        snapshot = df_hist[df_hist["data"] == ultima_data].copy()

        if "vencimento" in snapshot.columns:
            snapshot = snapshot.sort_values("vencimento").reset_index(drop=True)

        logger.info(
            f"TesouroDireto: curva NTN-B — {len(snapshot)} vértices em {ultima_data.date()}"
        )
        return snapshot

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_available_titles(self) -> list[str]:
        """Lista os tipos de títulos disponíveis no histórico.

        Returns:
            Lista de tipos únicos (ex: ["LFT", "NTN-B Principal", "LTN"]).
        """
        df = self.get_price_history()
        if "tipo" not in df.columns:
            return []
        return sorted(df["tipo"].dropna().unique().tolist())

    # ============================================================================
    # INTERNOS
    # ============================================================================

    @retry(max_attempts=3, delay=2.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_raw(self, url: str) -> requests.Response:
        """Faz GET com retry e rate limit."""
        response = self._session.get(url, timeout=self._timeout)
        response.raise_for_status()
        return response

    def _fetch_csv(self, url: str) -> pd.DataFrame:
        """Baixa CSV do Tesouro Transparente e normaliza colunas.

        Args:
            url: URL do CSV do Tesouro Transparente.

        Returns:
            DataFrame com colunas normalizadas via _COLUNAS_TESOURO.
        """
        logger.debug(f"TesouroDireto: baixando {url}")
        response = self._fetch_raw(url)

        # CSV do Tesouro usa separador ";" e encoding latin-1
        df = pd.read_csv(
            io.StringIO(response.text),
            sep=";",
            encoding="utf-8",
            decimal=",",
            thousands=".",
            dtype=str,  # Carrega tudo como str, converte depois
        )

        # Normaliza nomes de colunas
        df.columns = [c.strip() for c in df.columns]

        # Renomeia para nomes padronizados
        available = {k: v for k, v in _COLUNAS_TESOURO.items() if k in df.columns}
        df = df[list(available.keys())].rename(columns=available)

        logger.debug(f"TesouroDireto: {len(df)} linhas carregadas")
        return df
