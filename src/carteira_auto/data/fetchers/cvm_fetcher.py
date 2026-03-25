"""Fetcher da CVM (Comissão de Valores Mobiliários) — Dados Abertos.

Portal: https://dados.cvm.gov.br
API: https://dados.cvm.gov.br/dados/CIA_ABERTA/

Fontes de dados:
    - Cadastro de Companhias Abertas (CAD): mapeamento CNPJ ↔ ticker ↔ razão social
    - DFP (Demonstrações Financeiras Padronizadas): balanço, DRE, DFC anuais auditados
    - ITR (Informações Trimestrais): balanço, DRE, DFC trimestrais

Formato: CSVs comprimidos em ZIP, disponibilizados por período (ano/trimestre).
Sem autenticação. Dados oficiais com lag de ~45 dias após o período.

Fluxo típico:
    1. Mapeamento ticker → CNPJ via DDMFetcher.get_asset_list() (primário)
       ou CVMFetcher.get_company_registry() (fallback/validação)
    2. Busca de demonstrações financeiras via get_dfp() ou get_itr()
"""

from __future__ import annotations

import io
import zipfile

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

# URL base para dados abertos CVM
_BASE_URL = "https://dados.cvm.gov.br/dados"

# Mapeamento de tipo de demonstração → subdiretório e prefixo CVM
_STATEMENT_MAP = {
    "BPA": ("CIA_ABERTA/DOC/DFP/DADOS", "dfp_cia_aberta_BPA_con"),  # Balanço Ativo
    "BPP": ("CIA_ABERTA/DOC/DFP/DADOS", "dfp_cia_aberta_BPP_con"),  # Balanço Passivo
    "DRE": ("CIA_ABERTA/DOC/DFP/DADOS", "dfp_cia_aberta_DRE_con"),  # Demonst. Resultado
    "DFC_MD": (
        "CIA_ABERTA/DOC/DFP/DADOS",
        "dfp_cia_aberta_DFC_MD_con",
    ),  # Fluxo Caixa (dir.)
    "DVA": ("CIA_ABERTA/DOC/DFP/DADOS", "dfp_cia_aberta_DVA_con"),  # Valor Adicionado
}

_ITR_STATEMENT_MAP = {
    "BPA": ("CIA_ABERTA/DOC/ITR/DADOS", "itr_cia_aberta_BPA_con"),
    "BPP": ("CIA_ABERTA/DOC/ITR/DADOS", "itr_cia_aberta_BPP_con"),
    "DRE": ("CIA_ABERTA/DOC/ITR/DADOS", "itr_cia_aberta_DRE_con"),
    "DFC_MD": ("CIA_ABERTA/DOC/ITR/DADOS", "itr_cia_aberta_DFC_MD_con"),
}


class CVMFetcher:
    """Fetcher para dados abertos da CVM.

    Fornece demonstrações financeiras auditadas (DFP/ITR) e cadastro
    oficial de companhias abertas. Complementa o DDMFetcher com dados
    estruturados e auditados.

    Uso:
        fetcher = CVMFetcher()

        # Mapeamento automático ticker → CNPJ
        cnpj = fetcher.get_cnpj_by_ticker("PETR4")

        # DRE anual auditada
        dre = fetcher.get_dfp("33.000.167/0001-01", 2024, "DRE")

        # Balanço trimestral
        bpa = fetcher.get_itr("33.000.167/0001-01", 2024, 3, "BPA")
    """

    def __init__(self) -> None:
        self._timeout = settings.cvm.TIMEOUT
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "carteira_auto/1.0"})

    # ============================================================================
    # MAPEAMENTO TICKER → CNPJ
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_company_registry(self) -> pd.DataFrame:
        """Cadastro oficial de companhias abertas da CVM.

        Retorna DataFrame com CNPJ, razão social, código CVM, setor
        e situação (Ativo/Cancelado). Usado como fallback para
        mapeamento ticker→CNPJ quando DDM não disponibiliza.

        Returns:
            DataFrame com colunas: cnpj, razao_social, cod_cvm, setor, situacao.
        """
        url = f"{_BASE_URL}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
        logger.debug(f"CVM: buscando cadastro em {url}")

        response = self._fetch_raw(url)
        df = pd.read_csv(
            io.StringIO(response.text),
            sep=";",
            encoding="latin-1",
            dtype=str,
        )

        # Normaliza nomes de colunas
        df.columns = [c.strip().lower() for c in df.columns]

        # Seleciona e renomeia colunas relevantes
        col_map = {
            "cnpj_cia": "cnpj",
            "denom_social": "razao_social",
            "cod_cvm": "cod_cvm",
            "setor_ativ": "setor",
            "sit": "situacao",
        }
        available = {k: v for k, v in col_map.items() if k in df.columns}
        df = df[list(available.keys())].rename(columns=available)

        logger.info(f"CVM: cadastro carregado com {len(df)} companhias")
        return df

    @log_execution
    @cache_result(ttl_seconds=3600)
    def build_ticker_cnpj_map(self) -> dict[str, str]:
        """Constrói mapeamento ticker → CNPJ usando DDM como fonte primária.

        Estratégia:
            1. DDM /bolsa/lista-de-ativos (mais completo, retorna CNPJ diretamente)
            2. CVM cadastro como fallback para tickers não encontrados no DDM

        Returns:
            Dict {ticker: cnpj} — ex: {"PETR4": "33.000.167/0001-01"}
        """
        ticker_cnpj: dict[str, str] = {}

        # Fonte primária: DDM asset list
        try:
            from carteira_auto.data.fetchers.ddm_fetcher import DDMFetcher

            ddm = DDMFetcher()
            assets = ddm.get_asset_list()
            for asset in assets:
                ticker = asset.get("ticker") or asset.get("ativo", "")
                cnpj = asset.get("cnpj", "")
                if ticker and cnpj:
                    ticker_cnpj[ticker.upper()] = cnpj
            logger.info(f"CVM: {len(ticker_cnpj)} tickers mapeados via DDM")
        except Exception as e:
            logger.warning(f"CVM: DDM indisponível para mapeamento — {e}")

        # Fallback: CVM cadastro (tickers não mapeados pelo DDM)
        if len(ticker_cnpj) < 10:
            try:
                registry = self.get_company_registry()
                # CVM não tem ticker diretamente, mas o cod_cvm pode cruzar
                for _, row in registry.iterrows():
                    # Tenta derivar ticker do cod_cvm (heurística limitada)
                    cod = str(row.get("cod_cvm", "")).strip()
                    cnpj = str(row.get("cnpj", "")).strip()
                    if cod and cnpj:
                        ticker_cnpj[f"COD{cod}"] = cnpj
                logger.info(f"CVM: {len(ticker_cnpj)} entradas após fallback CVM")
            except Exception as e:
                logger.warning(f"CVM: falha no cadastro CVM — {e}")

        return ticker_cnpj

    def get_cnpj_by_ticker(self, ticker: str) -> str | None:
        """Retorna o CNPJ de uma empresa dado seu ticker B3.

        Args:
            ticker: Código do ativo na B3 (ex: "PETR4", "VALE3", "HGLG11").

        Returns:
            CNPJ formatado (ex: "33.000.167/0001-01") ou None se não encontrado.
        """
        # Normaliza: remove sufixo .SA se presente
        clean = ticker.upper().replace(".SA", "").strip()
        mapping = self.build_ticker_cnpj_map()

        # Tenta ticker exato
        if clean in mapping:
            return mapping[clean]

        # Tenta base do ticker (sem dígito final: PETR4 → PETR)
        base = clean.rstrip("0123456789F")
        for mapped_ticker, cnpj in mapping.items():
            if mapped_ticker.startswith(base) and len(mapped_ticker) <= len(clean) + 2:
                return cnpj

        logger.debug(f"CVM: CNPJ não encontrado para ticker '{ticker}'")
        return None

    # ============================================================================
    # DEMONSTRAÇÕES FINANCEIRAS ANUAIS (DFP)
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_dfp(self, cnpj: str, year: int, statement: str = "DRE") -> pd.DataFrame:
        """Demonstrações Financeiras Padronizadas (DFP) anuais auditadas.

        Busca dados consolidados do arquivo DFP do ano especificado.

        Args:
            cnpj: CNPJ da empresa (ex: "33.000.167/0001-01").
            year: Ano de referência (ex: 2024). Min: 2010.
            statement: Tipo de demonstração:
                - "DRE": Demonstração de Resultado
                - "BPA": Balanço Patrimonial Ativo
                - "BPP": Balanço Patrimonial Passivo
                - "DFC_MD": Fluxo de Caixa (método direto)
                - "DVA": Demonstração do Valor Adicionado

        Returns:
            DataFrame com colunas: cnpj, periodo, conta, descricao, valor.
            Filtrado apenas pela empresa (cnpj).

        Raises:
            ValueError: statement inválido.
            requests.HTTPError: Arquivo não encontrado na CVM.
        """
        if statement not in _STATEMENT_MAP:
            raise ValueError(
                f"Statement inválido: '{statement}'. "
                f"Válidos: {list(_STATEMENT_MAP.keys())}"
            )

        subdir, prefix = _STATEMENT_MAP[statement]
        url = f"{_BASE_URL}/{subdir}/{prefix}_{year}.zip"
        logger.debug(f"CVM DFP: buscando {statement} {year} para {cnpj}")

        df = self._fetch_zip_csv(url, f"{prefix}_{year}.csv")
        return self._filter_by_cnpj(df, cnpj)

    # ============================================================================
    # INFORMAÇÕES TRIMESTRAIS (ITR)
    # ============================================================================

    @log_execution
    @cache_result(ttl_seconds=86400)
    def get_itr(
        self, cnpj: str, year: int, quarter: int, statement: str = "DRE"
    ) -> pd.DataFrame:
        """Informações Trimestrais (ITR) da CVM.

        Args:
            cnpj: CNPJ da empresa.
            year: Ano (ex: 2024).
            quarter: Trimestre (1, 2, 3 ou 4 — onde 4 = DFP anual).
            statement: Tipo de demonstração (mesmas opções do get_dfp).

        Returns:
            DataFrame filtrado pela empresa.

        Raises:
            ValueError: quarter fora do range 1-4 ou statement inválido.
        """
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f"Trimestre inválido: {quarter}. Use 1, 2, 3 ou 4.")
        if statement not in _ITR_STATEMENT_MAP:
            raise ValueError(
                f"Statement inválido para ITR: '{statement}'. "
                f"Válidos: {list(_ITR_STATEMENT_MAP.keys())}"
            )

        subdir, prefix = _ITR_STATEMENT_MAP[statement]
        period = f"{year}Q{quarter}"
        url = f"{_BASE_URL}/{subdir}/{prefix}_{year}.zip"
        logger.debug(f"CVM ITR: buscando {statement} {period} para {cnpj}")

        df = self._fetch_zip_csv(url, f"{prefix}_{year}.csv")
        df_filtered = self._filter_by_cnpj(df, cnpj)

        # Filtra pelo trimestre específico quando há coluna de período
        date_cols = [
            c
            for c in df_filtered.columns
            if "dt_refer" in c.lower() or "periodo" in c.lower()
        ]
        if date_cols and quarter < 4:
            col = date_cols[0]
            df_filtered = df_filtered[
                df_filtered[col].astype(str).str.startswith(f"{year}-{quarter * 3:02d}")
                | df_filtered[col].astype(str).str.startswith(f"{year}-0{quarter}")
            ]

        return df_filtered

    # ============================================================================
    # CONVENIENCE: DFP por ticker
    # ============================================================================

    def get_dfp_by_ticker(
        self, ticker: str, year: int, statement: str = "DRE"
    ) -> pd.DataFrame:
        """DFP anual por ticker (resolve CNPJ automaticamente).

        Args:
            ticker: Código B3 (ex: "PETR4").
            year: Ano de referência.
            statement: Tipo de demonstração.

        Returns:
            DataFrame com a demonstração financeira.

        Raises:
            ValueError: Ticker não encontrado no mapeamento.
        """
        cnpj = self.get_cnpj_by_ticker(ticker)
        if not cnpj:
            raise ValueError(
                f"CNPJ não encontrado para ticker '{ticker}'. "
                "Verifique se o ativo está na B3 ou passe o CNPJ diretamente."
            )
        return self.get_dfp(cnpj, year, statement)

    def get_itr_by_ticker(
        self, ticker: str, year: int, quarter: int, statement: str = "DRE"
    ) -> pd.DataFrame:
        """ITR trimestral por ticker (resolve CNPJ automaticamente)."""
        cnpj = self.get_cnpj_by_ticker(ticker)
        if not cnpj:
            raise ValueError(f"CNPJ não encontrado para ticker '{ticker}'.")
        return self.get_itr(cnpj, year, quarter, statement)

    # ============================================================================
    # INTERNOS
    # ============================================================================

    @retry(max_attempts=3, delay=1.0)
    @rate_limit(calls_per_minute=30)
    def _fetch_raw(self, url: str) -> requests.Response:
        """Faz GET simples com retry e rate limit."""
        response = self._session.get(url, timeout=self._timeout)
        response.raise_for_status()
        return response

    def _fetch_zip_csv(self, url: str, filename: str) -> pd.DataFrame:
        """Baixa ZIP da CVM e extrai o CSV especificado.

        Args:
            url: URL do arquivo ZIP.
            filename: Nome do CSV dentro do ZIP.

        Returns:
            DataFrame com o conteúdo do CSV.
        """
        logger.debug(f"CVM: baixando {url}")
        response = self._fetch_raw(url)

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            # Procura arquivo case-insensitive
            names = zf.namelist()
            target = next(
                (n for n in names if n.lower() == filename.lower()),
                names[0] if names else None,
            )
            if not target:
                raise FileNotFoundError(
                    f"CVM: arquivo '{filename}' não encontrado no ZIP"
                )

            with zf.open(target) as f:
                df = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)

        df.columns = [c.strip().lower() for c in df.columns]
        logger.debug(f"CVM: {len(df)} linhas carregadas de {filename}")
        return df

    @staticmethod
    def _filter_by_cnpj(df: pd.DataFrame, cnpj: str) -> pd.DataFrame:
        """Filtra DataFrame pelo CNPJ da empresa."""
        # Normaliza CNPJ para comparação (remove pontuação)
        clean_cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")

        # Procura coluna de CNPJ
        cnpj_cols = [c for c in df.columns if "cnpj" in c.lower()]
        if not cnpj_cols:
            logger.warning("CVM: coluna CNPJ não encontrada no DataFrame")
            return df

        col = cnpj_cols[0]
        # Compara versão normalizada
        mask = df[col].str.replace(r"[.\-/]", "", regex=True) == clean_cnpj
        filtered = df[mask].copy()
        logger.debug(f"CVM: {len(filtered)} linhas para CNPJ {cnpj}")
        return filtered
