"""Loaders para importação de planilhas Excel."""

from pathlib import Path
from typing import Optional

import pandas as pd

from carteira_auto.config import constants, settings
from carteira_auto.core.models import Asset, Portfolio, SoldAsset
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution, timer

logger = get_logger(__name__)


class ExcelLoader:
    """Loader genérico para leitura de planilhas Excel.

    Fornece utilitários comuns de limpeza e leitura de abas.
    Subclasses implementam a lógica específica de cada tipo de planilha.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def _read_sheet(
        self,
        xl: pd.ExcelFile,
        sheet_name: str,
        columns: list[str],
        field_map: dict[str, str],
    ) -> pd.DataFrame:
        """Lê uma aba, filtra colunas conhecidas, renomeia e limpa."""
        if sheet_name not in xl.sheet_names:
            raise ValueError(f"Aba '{sheet_name}' não encontrada na planilha")

        df = pd.read_excel(xl, sheet_name=sheet_name)
        df = self._clean_dataframe(df)

        known_cols = [c for c in columns if c in df.columns]
        df = df[known_cols]

        rename_map = {col: field_map[col] for col in known_cols if col in field_map}
        df = df.rename(columns=rename_map)

        return df

    def _read_sheet_optional(
        self,
        xl: pd.ExcelFile,
        sheet_name: str,
        columns: list[str],
        field_map: dict[str, str],
    ) -> Optional[pd.DataFrame]:
        """Lê uma aba opcional — retorna None se não existir."""
        if sheet_name not in xl.sheet_names:
            logger.warning(f"Aba '{sheet_name}' não encontrada, ignorando")
            return None
        return self._read_sheet(xl, sheet_name, columns, field_map)

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove colunas sem nome e linhas totalmente vazias."""
        df = df.loc[:, df.columns.notna()]
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
        df = df.dropna(how="all")
        return df


class PortfolioLoader(ExcelLoader):
    """Importa a planilha de carteira e retorna um Portfolio.

    Lê as abas 'Carteira' (ativos) e 'Vendas' (vendas realizadas).

    Usage:
        loader = PortfolioLoader()  # usa path padrão de settings
        portfolio = loader.load_portfolio()

        loader = PortfolioLoader(Path("outra/planilha.xlsx"))
        portfolio = loader.load_portfolio()
    """

    def __init__(self, file_path: Optional[Path] = None):
        path = file_path or settings.paths.PORTFOLIO_FILE
        super().__init__(path)

    @log_execution
    @timer
    def load_portfolio(self) -> Portfolio:
        """Lê as abas Carteira e Vendas e retorna Portfolio."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Planilha não encontrada: {self.file_path}")

        logger.info(f"Carregando portfolio: {self.file_path}")

        xl = pd.ExcelFile(self.file_path)
        assets = self._load_assets(xl)
        sold_assets = self._load_sold_assets(xl)

        portfolio = Portfolio(assets=assets, sold_assets=sold_assets)

        logger.info(
            f"Portfolio carregado: {len(assets)} ativos, {len(sold_assets)} vendas"
        )
        return portfolio

    def _load_assets(self, xl: pd.ExcelFile) -> list[Asset]:
        """Lê a aba 'Carteira' e converte para lista de Asset."""
        df = self._read_sheet(
            xl,
            sheet_name=constants.SHEET_NAMES["carteira"],
            columns=constants.CARTEIRA_COLUMNS,
            field_map=constants.CARTEIRA_FIELD_MAP,
        )

        str_fields = {"preco_medio", "n_cotas_atual", "funcao_dialetica"}
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
                df[col] = pd.to_numeric(df[col], errors="coerce")

        assets = []
        for _, row in df.iterrows():
            ticker = row.get("ticker")
            if pd.isna(ticker) or ticker == "-":
                continue
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            assets.append(Asset(**row_dict))

        return assets

    def _load_sold_assets(self, xl: pd.ExcelFile) -> list[SoldAsset]:
        """Lê a aba 'Vendas' e converte para lista de SoldAsset."""
        df = self._read_sheet_optional(
            xl,
            sheet_name=constants.SHEET_NAMES["vendas"],
            columns=constants.VENDAS_COLUMNS,
            field_map=constants.VENDAS_FIELD_MAP,
        )
        if df is None:
            return []

        sold_assets = []
        for _, row in df.iterrows():
            if pd.isna(row.get("ticker")) or row.get("ticker") == "-":
                continue
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            sold_assets.append(SoldAsset(**row_dict))

        return sold_assets
