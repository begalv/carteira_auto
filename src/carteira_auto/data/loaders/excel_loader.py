"""Loader para importação da planilha de carteira."""

from pathlib import Path
from typing import Optional

import pandas as pd

from carteira_auto.config import constants, settings
from carteira_auto.core.models import Asset, PortfolioSnapshot, SoldAsset
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution, timer

logger = get_logger(__name__)


class ExcelLoader:
    """Importa a planilha de carteira e retorna um PortfolioSnapshot."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or (
            settings.paths.RAW_DATA_DIR / "Carteira 2026.xlsx"
        )

    @log_execution
    @timer
    def load(self) -> PortfolioSnapshot:
        """Lê as abas Carteira e Vendas e retorna PortfolioSnapshot."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Planilha não encontrada: {self.file_path}")

        logger.info(f"Carregando planilha: {self.file_path}")

        xl = pd.ExcelFile(self.file_path)
        assets = self._load_carteira_sheet(xl)
        sold_assets = self._load_vendas_sheet(xl)

        snapshot = PortfolioSnapshot(assets=assets, sold_assets=sold_assets)

        logger.info(
            f"Carteira carregada: {len(assets)} ativos, " f"{len(sold_assets)} vendas"
        )
        return snapshot

    def _load_carteira_sheet(self, xl: pd.ExcelFile) -> list[Asset]:
        """Lê a aba 'Carteira' e converte para lista de Asset."""
        sheet_name = constants.SHEET_NAMES["carteira"]
        if sheet_name not in xl.sheet_names:
            raise ValueError(f"Aba '{sheet_name}' não encontrada na planilha")

        df = pd.read_excel(xl, sheet_name=sheet_name)
        df = self._clean_dataframe(df)

        # Seleciona apenas colunas conhecidas que existem no DataFrame
        known_cols = [c for c in constants.CARTEIRA_COLUMNS if c in df.columns]
        df = df[known_cols]

        # Renomeia colunas usando o field map
        rename_map = {
            col: constants.CARTEIRA_FIELD_MAP[col]
            for col in known_cols
            if col in constants.CARTEIRA_FIELD_MAP
        }
        df = df.rename(columns=rename_map)

        # Campos que devem ser string (podem conter '-')
        str_fields = {"preco_medio", "n_cotas_atual", "funcao_dialetica"}
        # Campos que devem ser string sempre
        text_fields = {
            "fator",
            "ticker",
            "nome",
            "classe",
            "setor",
            "subsetor",
            "segmento",
        }

        for col in df.columns:
            if col in str_fields:
                df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)
            elif col not in text_fields:
                # Todos os demais campos numéricos: coerce para float
                df[col] = pd.to_numeric(df[col], errors="coerce")

        assets = []
        for _, row in df.iterrows():
            ticker = row.get("ticker")
            if pd.isna(ticker) or ticker == "-":
                continue
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            assets.append(Asset(**row_dict))

        return assets

    def _load_vendas_sheet(self, xl: pd.ExcelFile) -> list[SoldAsset]:
        """Lê a aba 'Vendas' e converte para lista de SoldAsset."""
        sheet_name = constants.SHEET_NAMES["vendas"]
        if sheet_name not in xl.sheet_names:
            logger.warning(f"Aba '{sheet_name}' não encontrada, retornando lista vazia")
            return []

        df = pd.read_excel(xl, sheet_name=sheet_name)
        df = self._clean_dataframe(df)

        known_cols = [c for c in constants.VENDAS_COLUMNS if c in df.columns]
        df = df[known_cols]

        rename_map = {
            col: constants.VENDAS_FIELD_MAP[col]
            for col in known_cols
            if col in constants.VENDAS_FIELD_MAP
        }
        df = df.rename(columns=rename_map)

        sold_assets = []
        for _, row in df.iterrows():
            if pd.isna(row.get("ticker")) or row.get("ticker") == "-":
                continue
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            sold_assets.append(SoldAsset(**row_dict))

        return sold_assets

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpa o DataFrame: remove colunas sem nome e linhas totalmente vazias."""
        # Remove colunas sem nome (None ou Unnamed)
        df = df.loc[:, df.columns.notna()]
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
        # Remove linhas completamente vazias
        df = df.dropna(how="all")
        return df
